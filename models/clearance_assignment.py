"""
Model for Clearance Assignments.
"""

from typing import Optional
from datetime import datetime, date
import requests
from util.db_connect import get_clearance_collection
from util.ccure_api import CcureApi
from .audit import Audit
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
            timeout=1
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
                timeout=1
            )
            assignment_ids = {item.get("GUID") for item in response.json()[1:]}

        return [ClearanceAssignment(clearance_id=_id) for _id in assignment_ids]

    @classmethod
    def assign(cls,
               assigner_id: str,
               assignee_ids: list[str],
               clearance_ids: list[str],
               start_time: Optional[date] = None,
               end_time: Optional[date] = None) -> list:
        """Assigns a list of clearances to a list of individuals."""
        now = datetime.utcnow()
        if start_time or end_time:  # then it's going to mongo
            new_assignments = []
            for assignee_id in assignee_ids:
                for clearance_id in clearance_ids:
                    new_assignments.append({
                        "assignee_id": assignee_id,
                        "assigner_id": assigner_id,
                        "clearance_id": clearance_id,
                        "state": "assign-pending" if start_time else "active",
                        "start_time": start_time,
                        "end_time": end_time,
                        "submitted_time": now
                    })
            assignment_collection = get_clearance_collection(
                "clearance_assignment")
            assignment_collection.insert_many(new_assignments)

        if start_time is None:  # then it's going to ccure
            new_assignments = []
            for assignee_id in assignee_ids:
                # TODO this is really inefficient. find a way to do this without creating a whole CA object.
                current_clearances = map(lambda ca: ca.clearance.id, cls.get_assignments_by_assignee(assignee_id))
                for clearance_id in clearance_ids:
                    if clearance_id not in current_clearances:
                        new_assignments.append({
                            "assignee_id": assignee_id,
                            "assigner_id": assigner_id,
                            "clearance_guid": clearance_id
                        })
            ccure_api = CcureApi()
            ccure_api.assign_clearances(new_assignments)

            # audit the new assignment
            Audit.add_many(audit_configs=[{
                "assigner_id": new_assignment["assigner_id"],
                "assignee_id": new_assignment["assignee_id"],
                "clearance_id": new_assignment["clearance_guid"],
                "clearance_name": CcureApi.get_clearance_name(
                    new_assignment["clearance_guid"]),
                "timestamp": now,
                "message": "Activating clearance"
            } for new_assignment in new_assignments])

        return len(assignee_ids) * len(clearance_ids)

    @staticmethod
    def revoke(assigner_id: str,
               assignee_ids: list[str],
               clearance_ids: list[str]):
        """Revokes a list of clearances from a list of individuals."""
        new_assignments = []
        for campus_id in assignee_ids:
            for clearance_id in clearance_ids:
                new_assignments.append({
                    "assignee_id": campus_id,
                    "assigner_id": assigner_id,
                    "clearance_id": clearance_id
                })
        ccure_api = CcureApi()
        ccure_api.revoke_clearances(new_assignments)

        # audit the new revocation
        now = datetime.utcnow()
        Audit.add_many(audit_configs=[{
            "assigner_id": new_assignment["assigner_id"],
            "assignee_id": new_assignment["assignee_id"],
            "clearance_id": new_assignment["clearance_id"],
            "clearance_name": CcureApi.get_clearance_name(
                new_assignment["clearance_id"]),
            "timestamp": now,
            "message": "Revoking clearance"
        } for new_assignment in new_assignments])
        return len(assignee_ids) * len(clearance_ids)
