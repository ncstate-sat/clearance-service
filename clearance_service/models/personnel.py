"""Model for Personnel"""

from datetime import datetime, timezone
from typing import Optional, Literal

from acslib.base.search import BooleanOperators
from acslib.ccure.types import ObjectType

from clearance_service.models import acs, filters
from clearance_service.models.clearance import Clearance
from clearance_service.models.door import Door
from clearance_service.models.door_group import DoorGroup
from clearance_service.util.db_connect import get_clearance_collection
from clearance_service.util.handle_requests import RequestException
from clearance_service.util.settings import C9K_PAGE_SIZE


class Personnel:
    """Any student, staff, or faculty member"""

    def __init__(self, personnel_data: dict):
        """
        `personnel_data` is a dict directly from an acs search result,
        but only including the requested personnel properties
        """
        personnel_data_copy = personnel_data.copy()
        self.first_name = personnel_data_copy.pop("FirstName", None)
        self.middle_name = personnel_data_copy.pop("MiddleName", None)
        self.last_name = personnel_data_copy.pop("LastName", None)
        self.email = personnel_data_copy.pop("EmailAddress", None)
        if "ObjectID" in personnel_data_copy:
            self.acs_id = personnel_data_copy.pop("ObjectID")

        # TODO make active a @property to avoid unnecessary acs calls for credentials
        self.active = not personnel_data_copy.pop("Disabled", None)

        for additional_property, val in personnel_data_copy.items():
            setattr(self, additional_property, val)

    def assign_liaison_permissions(self, clearances: list[dict]) -> dict:
        """
        Assign permission to assign certain clearances

        Parameters:
            clearances: data for clearances this person can assign
        """
        liaison_collection = get_clearance_collection("liaison")
        record = liaison_collection.find_one({"email": self.email})
        if record is not None:
            allowed_clearances = record.get("clearances")
            for new_clearance in clearances:
                if new_clearance not in allowed_clearances:
                    allowed_clearances.append(new_clearance)
            liaison_collection.update_one(
                {"email": self.email}, {"$set": {"clearances": allowed_clearances}}
            )
        else:
            record = {"email": self.email, "clearances": clearances}
            liaison_collection.insert_one(record)
        return record

    def revoke_liaison_permissions(self, clearance_ids: list[int]) -> dict:
        """
        Revoke permissions to assign certain clearances

        Parameters:
            clearance_ids: IDs for clearances this person should
                no longer be able to assign
        """
        liaison_collection = get_clearance_collection("liaison")
        record = liaison_collection.find_one({"email": self.email})

        if record is not None:
            items_to_remove = []
            allowed_clearances = record["clearances"] or []
            for current_clearance in allowed_clearances:
                if current_clearance["id"] in clearance_ids:
                    items_to_remove.append(current_clearance)
            for item in items_to_remove:
                allowed_clearances.remove(item)
            liaison_collection.update_one(
                {"email": self.email}, {"$set": {"clearances": allowed_clearances}}
            )
        else:
            record = {"email": self.email, "clearances": []}
            liaison_collection.insert_one(record)

        return record

    def get_liaison_permissions(self) -> list["Clearance"]:
        """Fetch a list of clearances this person can assign"""
        liaison_collection = get_clearance_collection("liaison")
        record = liaison_collection.find_one({"email": self.email})
        if record is None:
            return []
        return [
            Clearance(clearance.get("id"), clearance.get("name"))
            for clearance in record["clearances"]
        ]

    @staticmethod
    def find_one_liaison(email: str) -> Optional[dict]:
        """
        Get one liaison record from the `liaison` collection

        Parameters:
            email: the liaison's email address
        """
        liaison_coll = get_clearance_collection("liaison")
        liaison = liaison_coll.find_one({"email": email})
        if not liaison:
            return None
        return liaison

    @staticmethod
    def _find_one(search_filter, search_term) -> Optional["Personnel"]:
        """
        Find one person in acs by search term.

        Parameters:
            search_filter: The method for which the search term will search.
            search_term: The search query.

        Returns: one Personnel object or None
        """
        person_records = acs.personnel.search(
            terms=[search_term],
            search_filter=search_filter,
            page_size=C9K_PAGE_SIZE,
        )

        if person_records:
            person_record = {
                property: person_records[0][property]
                for property in search_filter.display_properties
            }
            person = Personnel(person_record)

            try:
                search_filter = filters.CredentialFilter(
                    lookups={"PersonnelID": filters.NFUZZ},
                    display_properties=["ObjectID", "PersonnelID", "Disabled"],
                )
                person_credentials = acs.credential.search(
                    terms=[person.acs_id],
                    search_filter=search_filter,
                    page_size=0,
                )

                credential_active_status = not all(
                    credential["Disabled"] for credential in person_credentials
                )
            except RequestException:
                pass

            # Personnel record and at least one credential MUST BOTH be active.
            person.active = person.active and credential_active_status
            return person

    @staticmethod
    def find_one(email: str, properties: list[str]) -> Optional["Personnel"]:
        """
        Find one person in acs by email address

        Parameters:
            email: the person's email address
            properties: additional personnel properties to return

        Returns: one Personnel object or None
        """
        search_filter = filters.PersonnelFilter(
            lookups={"EmailAddress": filters.NFUZZ},
            display_properties=list(set([
                "FirstName",
                "MiddleName",
                "LastName",
                "EmailAddress",
                "Disabled",
            ] + properties
            )),
        )
        person = Personnel._find_one(search_filter, email)
        return person

    @staticmethod
    def search_by_email(emails: list[str], properties: list[str]) -> list["Personnel"]:
        """
        Find a number of persons in acs given a list of email addresses

        Parameters:
            emails: a list of email addresses to search
            properties: additional properties to return from each person in the search results

        Returns: A list of Personnel objects
        """
        display_properties=list(set([
            "FirstName",
            "MiddleName",
            "LastName",
            "EmailAddress",
            "Disabled",
        ] + properties
        ))
        search_filter = filters.PersonnelFilter(
            lookups={"EmailAddress": filters.NFUZZ},
            display_properties=display_properties,
            outer_bool=BooleanOperators.OR,
        )
        person_records = acs.personnel.search(
            terms=emails,
            search_filter=search_filter,
            page_size=C9K_PAGE_SIZE,
        )

        if person_records:
            personnel = []
            for record in person_records:
                person_data = {prop_name: record[prop_name] for prop_name in display_properties}
                personnel.append(Personnel(person_data))
                # NOTE this is a different definition of 'active' than in _find_one
            return personnel
        else:
            return []

    @staticmethod
    def search(
        search_string: str,
        search_fields: dict[str, Literal["nfuzz", "fuzz", "rfuzz", "lfuzz"]],
        display_properties: list[str],
    ) -> list["Personnel"]:
        """
        Search personnel in acs by the the properties in `search_fields`,
        return users who match each search term.

        By default, return for each person:
          - FirstName
          - MiddleName
          - LastName
          - EmailAddress
          - Disabled

        Parameters:
            search_string: terms to search by, separated by whitespace
            search_fields: map of ACS fields to search to a search type to use -
              eg. `{"Text1": "rfuzz", "Property2": "nfuzz"}`
              - nfuzz: only include whole-word matches on the search term
              - fuzz: include matches that include the search term
              - lfuzz: include matches that end with the search term
              - rfuzz: include matches that begin with the search term

            display_properties: list of additional properties to return from each personnel object

        Returns: list of personnel matching the search
        """
        display_properties = list(set([
            "FirstName",
            "MiddleName",
            "LastName",
            "EmailAddress",
            "Disabled",
        ] + list(search_fields) + display_properties
        ))
        SEARCH_TYPES = {
            "nfuzz": filters.NFUZZ,
            "fuzz": filters.FUZZ,
            "lfuzz": filters.LFUZZ,
            "rfuzz": filters.RFUZZ,
        }
        search_filter = filters.PersonnelFilter(
            lookups = {
                prop: SEARCH_TYPES[search_type.lower()]
                for prop, search_type in search_fields.items()
            },
            display_properties=display_properties,
        )
        search_results = acs.personnel.search(
            terms=search_string.split(),
            search_filter=search_filter,
            page_size=C9K_PAGE_SIZE,
        )
        personnel_configs = [
            {prop: person.get(prop) for prop in display_properties}
            for person in search_results
        ]
        return [Personnel(config) for config in personnel_configs]

    @staticmethod
    def add_liaison(email: str) -> Optional["Personnel"]:
        """
        Add a liaison to the liaison collection.

        Parameters:
            email: The email address of the liaison.
        """
        acs_person = Personnel.find_one(email, ["ObjectID"])
        if acs_person is None:
            return

        liaison_collection = get_clearance_collection("liaison")
        liaison_collection.insert_one(
            {
                "email": email,
                "clearances": [],
            }
        )
        return acs_person

    @staticmethod
    def remove_liaison(email: str):
        """
        Remove a liaison from the liaison collection.

        Parameters:
            email: The email address of the liaison.

        Returns: The number of deleted records for this action.
        """
        liaison_collection = get_clearance_collection("liaison")
        deleted_count = liaison_collection.delete_one({"email": email}).deleted_count
        return deleted_count

    @staticmethod
    def get_doors(liaison_email: str) -> list:
        """Get all doors and door groups assignable by the given user"""
        clearances = Clearance.get_allowed(liaison_email)
        clearance_items = (
            acs.clearance_item.search(
                terms=[clearance.id for clearance in clearances],
                search_filter=filters.ClearanceItemFilter(
                    lookups={"ClearanceID": filters.NFUZZ},
                    outer_bool=BooleanOperators.OR,
                    display_properties=["DoorID", "DoorGroupID"],
                ),
                timeout=10,
            )
            if clearances
            else []
        )
        door_ids = {item["DoorID"] for item in clearance_items if item["DoorID"] is not None}
        doors = (
            [
                Door(acs_door["ObjectID"], acs_door["Name"])
                for acs_door in acs.ccure_object.search(
                    object_type=ObjectType.DOOR.complete,
                    terms=list(door_ids),
                    search_filter=filters.CcureFilter(
                        lookups={"ObjectID": filters.NFUZZ},
                        outer_bool=BooleanOperators.OR,
                        display_properties=["ObjectID", "Name"],
                    ),
                    timeout=10,
                )
            ]
            if door_ids
            else []
        )

        door_group_ids = {
            item["DoorGroupID"] for item in clearance_items if item["DoorGroupID"] is not None
        }
        door_groups = (
            [
                DoorGroup(acs_door_group["ObjectID"], acs_door_group["Name"])
                for acs_door_group in acs.group.search(
                    [door_group_id for door_group_id in door_group_ids],
                    filters.GroupFilter(
                        lookups={"ObjectID": filters.NFUZZ},
                        outer_bool=BooleanOperators.OR,
                        display_properties=["ObjectID", "Name"],
                    ),
                    timeout=10,
                )
            ]
            if door_group_ids
            else []
        )
        for door_group in door_groups:
            door_group.populate_doors()
        return doors + door_groups

    @classmethod
    def get_doors_ungrouped(cls, liaison_email: str) -> set[Door]:
        """
        Get all doors assignable by the given user as a flat set, without grouping by door group
        """
        grouped_doors = cls.get_doors(liaison_email)
        doors = set()
        for item in grouped_doors:
            if item.type == "door":
                doors.add(item)
            elif item.type == "door group":
                doors |= set(item.doors)
        return doors
