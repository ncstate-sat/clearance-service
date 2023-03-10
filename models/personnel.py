"""Model for Personnel"""

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
        return ClearanceAssignment.get_clearance_ids_by_assignee(self.campus_id)

    def assign(self,
               assigner_id: str,
               clearances: list[str],
               start_time: Optional[datetime.datetime] = None,
               end_time: Optional[datetime.datetime] = None) -> int:
        """
        Assign clearances to this person

        Parameters:
            assigner_id: the campus ID of the person assigning clearances
            clearances: list of clearance GUIDs to be assigned
            start_time: the time the assignment should go into effect
            end_time: the time the assignment should expire

        Returns: the number of changes made
        """
        return ClearanceAssignment.assign(
            assigner_id,
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

    def assign_liaison_permissions(self, clearance_ids: list[str]) -> dict:
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
            allowed_clearance_ids = record["clearance_ids"] or []
            for clearance_id in clearance_ids:
                if clearance_id not in allowed_clearance_ids:
                    allowed_clearance_ids.append(clearance_id)
            record["clearance_ids"] = allowed_clearance_ids
            liaison_permissions_collection.update_one(
                {"campus_id": self.campus_id},
                {"$set": {"clearance_ids": record["clearance_ids"]}})
        else:
            record = {
                "campus_id": self.campus_id,
                "clearance_ids": clearance_ids
            }
            liaison_permissions_collection.insert_one(record)
        return record

    def revoke_liaison_permissions(self, clearance_ids: list[str]) -> dict:
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
            allowed_clearance_ids = record["clearance_ids"] or []
            for cl_id in clearance_ids:
                if cl_id in allowed_clearance_ids:
                    allowed_clearance_ids.remove(cl_id)
            record["clearance_ids"] = allowed_clearance_ids
            liaison_permissions_collection.update_one(
                {"campus_id": self.campus_id},
                {"$set": {"clearance_ids": record["clearance_ids"]}})
        else:
            record = {
                "campus_id": self.campus_id,
                "clearance_ids": []
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
        return [Clearance(guid) for guid in record["clearance_ids"]]

    @staticmethod
    def search(search_terms) -> list["Personnel"]:
        """
        Use the CCure api to search personnel by campus ID and email,
        then return users who match each search term

        Parameters:
            search_terms: terms to search by, separated by whitespace

        Returns: list of Personnel objects that match the search
        """
        ccure_api = CcureApi()
        query_route = "/victorwebservice/api/Objects/FindObjsWithCriteriaFilter"
        url = ccure_api.base_url + query_route
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
                "session-id": ccure_api.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == 200:
            return [Personnel(
                person["FirstName"],
                person["MiddleName"],
                person["LastName"],
                person["Text14"],  # email
                person["Text1"]  # campus_id
            ) for person in response.json()]
        print(response.text)
        return []
