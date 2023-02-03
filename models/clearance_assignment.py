"""
Model for Clearance Assignments.
"""

from typing import Optional
from datetime import datetime, date
import requests
from util.db_connect import get_clearance_collection
from util.ccure_api import CcureApi
from .clearance import Clearance


class ClearanceAssignment:
    """
    A record of a clearance being assigned to an individual.
    """

    def __init__(self,
                 assigner_id: str = None,
                 assignee_id: str = None,
                 clearance_id: str = None,
                 state: str = None,
                 start_time: datetime = None,
                 end_time: datetime = None,
                 submitted_time: datetime = None) -> None:
        """Initialize a ClearanceAssignment object"""
        self.assigner_id = assigner_id
        self.assignee_id = assignee_id
        self.clearance = Clearance(clearance_id)
        self.state = state
        self.start_time = start_time
        self.end_time = end_time
        self.submitted_time = submitted_time

    @staticmethod
    def get_assignments_by_assignee(
        assignee_id: str
    ) -> list["ClearanceAssignment"]:
        """
        Fetch an individual's current clearances

        :param str assignee_id: The Campus ID of the individual
            who was assigned the clearances.
        :return list[ClearanceAssignment]: the individual's clearances
        """
        clearance_assignment = get_clearance_collection("clearance_assignment")
        clearance_assignment_data = clearance_assignment.aggregate([
            # get all assign and revoke requests
            {
                "$match": {"assignee_id": assignee_id}
            },
            # sort the requests oldest to newest
            {
                "$sort": {"submitted_time": 1}
            },
            {
                "$project": {
                    "_id": 0,
                    "clearance_id": 1,
                    "state": 1
                }
            }
        ])

        # first get object ids for clearances assigned to assignee_id
        ccure_api = CcureApi()
        assignee_object_id = ccure_api.get_object_id(assignee_id)
        route = "/victorwebservice/api/Objects/GetAllWithCriteria"
        url = ccure_api.base_url + route
        request_json = {
            "TypeFullName": ("SoftwareHouse.NextGen.Common.SecurityObjects."
                             "PersonnelClearancePairTimed"),
            "WhereClause": f"PersonnelID = {assignee_object_id}"
        }
        response = requests.post(
            url,
            json=request_json,
            headers={
                "session-id": ccure_api.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=5000
        )
        if response.status_code == 404:
            return []
        clearance_ids = [pair.get("ClearanceID") for pair in response.json()]

        # then get the guids for those clearances
        if clearance_ids:
            route = "/victorwebservice/api/v2/Personnel/ClearancesForAssignment"
            query = " OR ".join(f"ObjectID = {_id}"for _id in clearance_ids)
            request_json = {
                "partitionList": [],
                "whereClause": query,
                "pageSize": 0,
                "pageNumber": 1,
                "sortColumnName": "",
                "whereArgList": [],
                "propertyList": ["Name"],
                "explicitPropertyList": []
            }
            response = requests.post(
                ccure_api.base_url + route,
                json=request_json,
                headers={
                    "session-id": ccure_api.get_session_id(),
                    "Access-Control-Expose-Headers": "session-id"
                },
                timeout=5000
            )
            assignment_ids = {item.get("GUID") for item in response.json()[1:]}

        # then go over the new requests to get all current clearances:
        for assignment in clearance_assignment_data:
            if assignment["state"] in ("active",
                                       "assign-pending",
                                       "assign-pushed"):
                assignment_ids.add(assignment["clearance_id"])
            else:  # if state is "revoke-pending" or "revoke-pushed"
                try:
                    assignment_ids.remove(assignment["clearance_id"])
                except KeyError:
                    continue

        return [ClearanceAssignment(clearance_id=_id) for _id in assignment_ids]

    @staticmethod
    def assign(campus_ids: list[str],
               assigner_id: str,
               clearance_ids: list[str],
               start_time: Optional[date] = None,
               end_time: Optional[date] = None) -> list:
        """Assigns a list of clearances to a list of individuals."""
        new_assignments = []
        for campus_id in campus_ids:
            for clearance_id in clearance_ids:
                new_assignments.append({
                    "assignee_id": campus_id,
                    "assigner_id": assigner_id,
                    "clearance_id": clearance_id,
                    "state": "assign-pending",
                    "start_time": start_time,
                    "end_time": end_time,
                    "submitted_time": datetime.utcnow()
                })
        assignment_collection = get_clearance_collection(
            "clearance_assignment")
        result = assignment_collection.insert_many(new_assignments)
        return [str(_id) for _id in result.inserted_ids]

    @staticmethod
    def revoke(assigner_id: str,
               campus_ids: list[str],
               clearance_ids: list[str]):
        """Revokes a list of clearances from a list of individuals."""
        new_assignments = []
        for campus_id in campus_ids:
            for clearance_id in clearance_ids:
                new_assignments.append({
                    "assignee_id": campus_id,
                    "assigner_id": assigner_id,
                    "clearance_id": clearance_id,
                    "state": "revoke-pending",
                    "start_time": None,
                    "end_time": None,
                    "submitted_time": datetime.utcnow()
                })
        assignment_collection = get_clearance_collection(
            "clearance_assignment")
        result = assignment_collection.insert_many(new_assignments)
        return [str(_id) for _id in result.inserted_ids]
