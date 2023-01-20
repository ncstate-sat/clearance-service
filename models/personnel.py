"""
Model for Personnel.
"""

import os
from typing import Union
import datetime
import requests
from util.db_connect import get_clearance_collection
from util.ccure_api import CcureApi
from .clearance_assignment import ClearanceAssignment
from .clearance import Clearance


class Personnel:
    """
    Any student, staff, or faculty member.
    """

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

    def get_full_name(self, use_middle_name: bool = True) -> str:
        """
        Returns the full name of the person.

        :params middle_name: Whether or not to include the middle name
        in the full name.
        """

        full_name = self.first_name

        if use_middle_name and self.middle_name:
            full_name += " " + self.middle_name

        full_name += " " + self.last_name

        return full_name.strip()

    def clearances(self) -> list[str]:
        """
        Returns a list of the clearance IDs assigned to this person.
        """
        assignment_collection = get_clearance_collection(
            "clearance_assignment")
        clearance_data = assignment_collection.find(
            {"assignee_id": self.campus_id}
        )
        return [data["clearance_id"] for data in clearance_data]

    def assign(self,
               assigner_id: str,
               clearances: list[str],
               start_time: Union[datetime.datetime, None] = None,
               end_time: Union[datetime.datetime, None] = None):
        """
        Assigns clearances to this person.

        :param clearances: List of clearances to assign.
        """
        return ClearanceAssignment.assign(
            [self.campus_id],
            assigner_id,
            clearances,
            start_time,
            end_time
        )

    def revoke(self, assigner_id: str, clearances: list[str]):
        """
        Revokes clearances from this person.

        :param str assigner_id: Campus ID of the user revoking the clearance
        :param list clearances: List of clearances to revoke.
        """
        return ClearanceAssignment.revoke(
            assigner_id,
            [self.campus_id],
            clearances
        )

    def assign_liaison_permissions(self, clearance_ids: list[str]):
        """
        Assigns permissions to assign certain clearances.

        :param str clearance_ids: Clearance IDs which this person can assign.
        """
        liaison_permissions_collection = get_clearance_collection(
            'liaison-clearance-permissions')
        record = liaison_permissions_collection.find_one({
            'campus_id': self.campus_id})
        if record is not None:
            allowed_clearance_ids = record['clearance_ids'] or []
            for cl_id in clearance_ids:
                if cl_id not in allowed_clearance_ids:
                    allowed_clearance_ids.append(cl_id)
            record['clearance_ids'] = allowed_clearance_ids
            liaison_permissions_collection.update_one(
                {'campus_id': self.campus_id},
                {'$set': {'clearance_ids': record['clearance_ids']}})
        else:
            record = {
                'campus_id': self.campus_id,
                'clearance_ids': clearance_ids
            }
            liaison_permissions_collection.insert_one(record)
        return record

    def revoke_liaison_permissions(self, clearance_ids: list[str]):
        """
        Revokes permissions to assign certain clearances.

        :param str clearance_ids: Clearance IDs which this person should
        no longer be able to assign.
        """
        liaison_permissions_collection = get_clearance_collection(
            'liaison-clearance-permissions')
        record = liaison_permissions_collection.find_one({
            'campus_id': self.campus_id})

        if record is not None:
            allowed_clearance_ids = record['clearance_ids'] or []
            for cl_id in clearance_ids:
                if cl_id in allowed_clearance_ids:
                    allowed_clearance_ids.remove(cl_id)
            record['clearance_ids'] = allowed_clearance_ids
            liaison_permissions_collection.update_one(
                {'campus_id': self.campus_id},
                {'$set': {'clearance_ids': record['clearance_ids']}})
        else:
            record = {
                'campus_id': self.campus_id,
                'clearance_ids': []
            }
            liaison_permissions_collection.insert_one(record)

        return record

    def get_liaison_permissions(self) -> list[str]:
        """
        Fetches a list of permissions which this person can assign.
        """
        liaison_permissions_collection = get_clearance_collection(
            'liaison-clearance-permissions')
        record = liaison_permissions_collection.find_one({
            'campus_id': self.campus_id})
        if record is not None:
            return [Clearance(cl_id) for cl_id in record['clearance_ids']]
        else:
            return []

    @staticmethod
    def search(search_terms) -> list["Personnel"]:
        """
        Use the CCURE api to search personnel.
        Searches first name, last name, campus_id, and email,
        then returns users who match each search term
        :param str search_terms: terms to search by, separated by whitespace
        :returns list[Personnel]: the people who match the search
        """
        session_id = CcureApi.get_session_id()
        base_url = os.getenv("CCURE_BASE_URL")
        query_route = "/victorwebservice/api/Objects/FindObjsWithCriteriaFilter"
        url = base_url + query_route
        search_terms = search_terms or ""

        term_queries = [
            (f"(FirstName LIKE '%{term}%' OR "
             f"LastName LIKE '%{term}%' OR "
             f"Text1 LIKE '%{term}%' OR "  # campus_id
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
                "session-id": session_id,
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=5000
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
