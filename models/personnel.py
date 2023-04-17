"""Model for Personnel"""

from fastapi import status
from typing import Optional
import datetime
import requests
from util.db_connect import get_clearance_collection
from util.ccure_api import CcureApi
from .clearance_assignment import ClearanceAssignment
from .clearance import Clearance


class Personnel:
    """Any student, staff, or faculty member"""

    first_name: str
    middle_name: str
    last_name: str
    email: str
    campus_id: str

    def __init__(self,
                 first_name=None,
                 middle_name=None,
                 last_name=None,
                 email=None,
                 campus_id=None):
        self.first_name = first_name
        self.middle_name = middle_name
        self.last_name = last_name
        self.email = email
        self.campus_id = campus_id

    def get_full_name(self, use_middle_name: bool = False) -> str:
        """
        Return the full name of the person

        Parameters:
            use_middle_name: Whether or not to include the middle name
                in the full name
        """

        full_name = self.first_name

        if use_middle_name and self.middle_name:
            full_name += " " + self.middle_name

        full_name += " " + self.last_name

        return full_name.strip()

    def clearances(self) -> list[str]:
        """Return a list of the clearance GUIDs assigned to this person"""
        clearances = ClearanceAssignment.get_clearances_by_assignee(
            self.campus_id)
        return [clearance.id for clearance in clearances]

    def assign(self,
               assigner_email: str,
               clearances: list[str],
               start_time: Optional[datetime.datetime] = None,
               end_time: Optional[datetime.datetime] = None) -> int:
        """
        Assign clearances to this person

        Parameters:
            assigner_email: the email address of the person assigning clearances
            clearances: list of clearance GUIDs to be assigned
            start_time: the time the assignment should go into effect
            end_time: the time the assignment should expire

        Returns: the number of changes made
        """
        return ClearanceAssignment.assign(
            assigner_email,
            [self.campus_id],
            clearances,
            start_time,
            end_time
        )

    def revoke(self, assigner_id: str, clearances: list[str]) -> int:
        """
        Revokes clearances from this person.

        Parameters:
            assigner_id: the campus ID of the person revoking clearances
            clearances: list of clearance GUIDs to be revoked

        Returns: the number of changes made
        """
        return ClearanceAssignment.revoke(
            assigner_id,
            [self.campus_id],
            clearances
        )

    def assign_liaison_permissions(self, clearances: list[dict]) -> dict:
        """
        Assign permission to assign certain clearances

        Parameters:
            clearance_ids: GUIDs for clearances this person can assign
        """
        liaison_permissions_collection = get_clearance_collection(
            "liaison-clearance-permissions")
        record = liaison_permissions_collection.find_one({
            "campus_id": self.campus_id})
        if record is not None:
            allowed_clearances = record.get("clearances")
            for new_clearance in clearances:
                if new_clearance not in allowed_clearances:
                    allowed_clearances.append(new_clearance)
            liaison_permissions_collection.update_one(
                {"campus_id": self.campus_id},
                {"$set": {"clearances": allowed_clearances}})
        else:
            record = {
                "campus_id": self.campus_id,
                "email": self.email,
                "clearances": clearances
            }
            liaison_permissions_collection.insert_one(record)
        return record

    def revoke_liaison_permissions(self, clearance_guids: list[str]) -> dict:
        """
        Revoke permissions to assign certain clearances

        Parameters:
            clearance_ids: GUIDs for clearances this person should
                no longer be able to assign
        """
        liaison_permissions_collection = get_clearance_collection(
            "liaison-clearance-permissions")
        record = liaison_permissions_collection.find_one({
            "campus_id": self.campus_id})

        if record is not None:
            items_to_remove = []
            allowed_clearances = record["clearances"] or []
            for current_clearance in allowed_clearances:
                if current_clearance["guid"] in clearance_guids:
                    items_to_remove.append(current_clearance)
            for item in items_to_remove:
                allowed_clearances.remove(item)
            liaison_permissions_collection.update_one(
                {"campus_id": self.campus_id},
                {"$set": {"clearances": allowed_clearances}})
        else:
            record = {
                "campus_id": self.campus_id,
                "email": self.email,
                "clearances": []
            }
            liaison_permissions_collection.insert_one(record)

        return record

    def get_liaison_permissions(self) -> list["Clearance"]:
        """Fetch a list of clearances this person can assign"""
        liaison_permissions_collection = get_clearance_collection(
            "liaison-clearance-permissions")
        record = liaison_permissions_collection.find_one({
            "campus_id": self.campus_id})
        if record is None:
            return []
        return [Clearance(clearance.get("guid"),
                          clearance.get("id"),  # the ccure_id.
                          clearance.get("name"))
                for clearance in record["clearances"]]

    @staticmethod
    def find_one(campus_id: str) -> "Personnel":
        """
        Use the CCure api to find one person by campus ID

        Parameters:
            campus_id: the person's campus ID

        Returns: one Personnel object or None
        """
        query_route = "/victorwebservice/api/Objects/FindObjsWithCriteriaFilter"
        url = CcureApi.base_url + query_route

        request_json = {
            "TypeFullName": "Personnel",
            "WhereClause": f"Text1 = '{campus_id}'"
        }
        response = requests.post(
            url,
            json=request_json,
            headers={
                "session-id": CcureApi.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == status.HTTP_200_OK:
            json = response.json()[0]
            return Personnel(
                json["FirstName"],
                json["MiddleName"],
                json["LastName"],
                json["Text14"],  # email
                json["Text1"]  # campus_id
            )
        print(response.text)

    @staticmethod
    def search(search_terms) -> list["Personnel"]:
        """
        Use the CCure api to search personnel by campus ID and email,
        then return users who match each search term

        Parameters:
            search_terms: terms to search by, separated by whitespace

        Returns: list of Personnel objects that match the search
        """
        query_route = "/victorwebservice/api/Objects/FindObjsWithCriteriaFilter"
        url = CcureApi.base_url + query_route
        search_terms = search_terms or ""

        term_queries = [
            (f"(Text1 LIKE '%{term}%' OR "  # campus_id
             f"Text14 LIKE '%{term}%')")  # email
            for term in search_terms.split()
        ]
        request_json = {
            "TypeFullName": "Personnel",
            "WhereClause": " AND ".join(term_queries)
        }
        response = requests.post(
            url,
            json=request_json,
            headers={
                "session-id": CcureApi.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == status.HTTP_200_OK:
            return [Personnel(
                person["FirstName"],
                person["MiddleName"],
                person["LastName"],
                person["Text14"],  # email
                person["Text1"]  # campus_id
            ) for person in response.json()]
        print(response.text)
        return []
