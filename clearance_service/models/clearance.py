"""Model for Clearances"""

from math import ceil
from typing import Optional

from acslib.base.search import BooleanOperators
from sat.logs import SATLogger

from clearance_service.models import acs, filters
from clearance_service.models.door import Door
from clearance_service.util.db_connect import get_clearance_collection
from clearance_service.util.sanitize_string import sanitize_string

logger = SATLogger(__name__)


class Clearance:
    """ACS clearance objects"""

    def __init__(self, _id: int, name: Optional[str] = None) -> None:
        """
        Parameters:
            _id: the clearance's acs object ID
            name: the name of the clearance in acs
        """
        self.id = _id
        if name:
            self.name = name
        else:
            self.name = acs.clearance.get_property(self.id, "Name")

    @staticmethod
    def get(
        query: Optional[str] = "", page_size: Optional[int] = None, page_num: Optional[int] = None
    ) -> list["Clearance"]:
        """
        Get a list of clearances whose names match the `query` substring.
        Limited to C9K_PAGE_SIZE results.

        Parameters:
            query: A regex string matching clearance names.
                Default to matching everything.

        Returns: A list of clearance objects
        """
        query_str = (query or "").strip()
        clearances = acs.clearance.search(
            terms=[query_str], page_size=page_size, page_number=page_num
        )
        return [
            Clearance(
                _id=clearance.get("ObjectID", 0),
                name=clearance.get("Name", ""),
            )
            for clearance in clearances
        ]

    @classmethod
    def get_all(cls) -> dict:
        """
        Get a list of all clearances

        Returns: A list of clearance objects
        """
        page_size = 10000
        clearances = []
        clearances_count = acs.clearance.count()
        for page in range(ceil(clearances_count / page_size)):
            clearances.extend(
                acs.clearance.search(page_number=page + 1, page_size=page_size, timeout=30)
            )
        return {
            clearance.get("ObjectID", ""): {
                "name": clearance.get("Name", ""),
                "id": clearance.get("ObjectID", ""),
            }
            for clearance in clearances
        }

    @staticmethod
    def get_by_ids(ids: list[int]) -> list[dict]:
        """
        Get a list of clearance records for use in the liaison collection

        Parameters:
            ids: list of clearance ids to get data for

        Returns: list of dicts including the id and name of the given clearances
        """
        search_filter = filters.ClearanceFilter(
            lookups={"ObjectID": filters.NFUZZ},
            outer_bool=BooleanOperators.OR,
            display_properties=["ObjectID", "Name"],
        )
        clearances = acs.clearance.search(ids, search_filter, page_size=len(ids))
        return [
            {"id": clearance.get("ObjectID"), "name": clearance.get("Name")}
            for clearance in clearances
        ]

    @staticmethod
    def get_allowed(email: Optional[str] = None, search: str = "") -> list["Clearance"]:
        """
        Get all clearances a liaison can assign

        Parameters:
            email: address of the liaison whose permissions are being checked
            search: only return clearances whose names include this substring

        Returns: A list of allowed Clearance objects
        """
        if not email:
            raise RuntimeError("An email address is required.")

        collection = get_clearance_collection("liaison")
        allowed_clearances = collection.aggregate(
            [
                {"$match": {"email": email}},
                {"$unwind": "$clearances"},
                {
                    "$project": {
                        "_id": "$clearances.id",
                        "name": "$clearances.name",
                    }
                },
                # case insensitive
                {"$match": {"name": {"$regex": sanitize_string(search), "$options": "i"}}},
            ]
        )

        return [Clearance(**clearance) for clearance in allowed_clearances]

    @staticmethod
    def get_doors_by_clearance_id(
        clearance_ids: list[str], cached_door_names: dict[int, Optional[str]]
    ) -> dict[int, dict[int, Optional[str]]]:
        """
        Get all doors by clearance ID, including doors granted through a door group.

        Parameters:
            clearance_ids: A list of clearance IDs of which to find associated doors.
            cached_door_names: Door names keyed by door ID. Doors missing from it are
                looked up in CCure.

        Returns:
            A map of clearances IDs with associated doors.

            Example:
                {
                    5000: {
                        5001: VRB-B-B141-Room Name-BS
                    }
                }
        """

        # Set up filters for searching ACS items.
        clearance_item_search_filter = filters.ClearanceItemFilter(
            lookups={"ClearanceID": filters.NFUZZ},
            outer_bool=BooleanOperators.OR,
            display_properties=[
                "ClearanceID",
                "DoorID",
                "ElevatorID",
                "ScheduleID",
                "DoorGroupID",
                "ElevatorGroupID",
            ],
        )

        # Query the many-to-many relationship between clearances and doors.
        clearance_items = acs.clearance_item.search(
            terms=clearance_ids,
            search_filter=clearance_item_search_filter,
            timeout=35,
            page_size=99999,
        )
        door_ids = [item["DoorID"] for item in clearance_items if item["DoorID"] is not None]

        # A door group can be shared by more than one of the given clearances, so
        # each door group maps to a set of clearance IDs, not just one.
        clearance_ids_by_door_group_id: dict[int, set[int]] = {}
        for item in clearance_items:
            if item.get("DoorGroupID"):
                clearance_ids_by_door_group_id.setdefault(item["DoorGroupID"], set()).add(
                    item["ClearanceID"]
                )

        # Resolve door groups into their member doors, and track which clearances
        # reach each member door via that group.
        door_ids_by_clearance_id: dict[int, set[int]] = {}
        if clearance_ids_by_door_group_id:
            group_member_search_filter = filters.GroupMemberFilter(
                lookups={"GroupID": filters.NFUZZ},
                outer_bool=BooleanOperators.OR,
                display_properties=["TargetObjectID", "GroupID"],
            )
            group_members = acs.group_member.search(
                terms=list(clearance_ids_by_door_group_id),
                search_filter=group_member_search_filter,
                timeout=35,
                page_size=99999,
            )
            for member in group_members:
                for clearance_id in clearance_ids_by_door_group_id.get(member["GroupID"], ()):
                    door_ids_by_clearance_id.setdefault(clearance_id, set()).add(
                        member["TargetObjectID"]
                    )

        all_door_ids = set(door_ids) | {
            door_id for door_ids_ in door_ids_by_clearance_id.values() for door_id in door_ids_
        }

        door_names = Clearance._get_door_names(all_door_ids, cached_door_names)

        # Map door names to the clearance-to-door relationships.
        clearance_doors: dict[int, dict[int, Optional[str]]] = {}
        for item in clearance_items:
            door_id = item["DoorID"]
            clearance_id = item["ClearanceID"]
            if door_id and door_id in door_names:
                clearance_doors.setdefault(clearance_id, {})[door_id] = door_names[door_id] or None

        # Map door names found via door groups to the owning clearances.
        for clearance_id, group_door_ids in door_ids_by_clearance_id.items():
            for door_id in group_door_ids:
                if door_id in door_names:
                    clearance_doors.setdefault(clearance_id, {})[door_id] = (
                        door_names[door_id] or None
                    )

        return clearance_doors

    @staticmethod
    def _get_door_names(
        door_ids: set[int], cached_door_names: dict[int, Optional[str]]
    ) -> dict[int, Optional[str]]:
        """Get door names from the cache, looking up any doors missing from it in CCure."""
        door_names = {
            door_id: cached_door_names[door_id]
            for door_id in door_ids
            if door_id in cached_door_names
        }
        uncached_door_ids = list(door_ids - door_names.keys())
        if uncached_door_ids:
            logger.info(
                f"{len(uncached_door_ids)} door IDs not found in the door cache, "
                "fetching their names from CCure."
            )
            door_names.update(Door.get_names_by_ids(uncached_door_ids))
        return door_names
