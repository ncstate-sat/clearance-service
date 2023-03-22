"""Model for Clearance Assignments"""

from typing import Optional
from datetime import datetime, date
import requests
from util.db_connect import get_clearance_collection
from util.ccure_api import CcureApi
from .audit import Audit
from .clearance import Clearance


class ClearanceAssignment:
    """A record of a clearance being assigned to an individual"""

    def __init__(self,
                 assigner_id: str = None,
                 assignee_id: str = None,
                 clearance_id: str = None,
                 clearance_name: str = None,
                 state: str = None,
                 start_time: datetime = None,
                 end_time: datetime = None,
                 submitted_time: datetime = None) -> None:
        """Initialize a ClearanceAssignment object"""
        self.assigner_id = assigner_id
        self.assignee_id = assignee_id
        self.clearance = Clearance(clearance_id, clearance_name)
        self.state = state
        self.start_time = start_time
        self.end_time = end_time
        self.submitted_time = submitted_time

    @staticmethod
    def get_clearances_by_assignee(assignee_id: str) -> list["Clearance"]:
        """
        Fetch an indiviual's clearances

        Parameters:
            assignee_id: the individual's campus id

        Returns: A list of clearances
        """
        # first get object ids for clearances assigned to assignee_id
        assignee_object_id = CcureApi.get_object_id(assignee_id)
        route = "/victorwebservice/api/Objects/GetAllWithCriteria"
        url = CcureApi.base_url + route
        request_json = {
            "TypeFullName": ("SoftwareHouse.NextGen.Common.SecurityObjects."
                             "PersonnelClearancePairTimed"),
            "WhereClause": f"PersonnelID = {assignee_object_id}"
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
        if response.status_code == 404:
            return []
        clearance_ids = [pair.get("ClearanceID") for pair in response.json()]

        # then get the guids for those clearances
        if clearance_ids:
            route = "/victorwebservice/api/v2/Personnel/ClearancesForAssignment"
            query = " OR ".join(f"ObjectID = {_id}" for _id in clearance_ids)
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
                CcureApi.base_url + route,
                json=request_json,
                headers={
                    "session-id": CcureApi.get_session_id(),
                    "Access-Control-Expose-Headers": "session-id"
                },
                timeout=1
            )
            return [Clearance(item.get("GUID"), item.get("Name")) for item in response.json()[1:]]
        return []

    @classmethod
    def get_assignments_by_assignee(
        cls,
        assignee_id: str
    ) -> list["ClearanceAssignment"]:
        """
        Fetch an individual's current clearances

        Parameters:
            assignee_id: The Campus ID of the individual
                who was assigned the clearances.

        Returns: A list of the individual's clearances
        """
        clearances = cls.get_clearances_by_assignee(assignee_id)
        return [ClearanceAssignment(clearance_id=clearance.id,
                                    clearance_name=clearance.name)
                for clearance in clearances]

    @classmethod
    def assign(cls,
               assigner_id: str,
               assignee_ids: list[str],
               clearance_ids: list[str],
               start_time: Optional[date] = None,
               end_time: Optional[date] = None) -> int:
        """
        Assign a list of clearances to a list of individuals

        Parameters:
            assigner_id: the campus ID of the person assigning clearances
            assignee_ids: list of campus IDs for people getting clearances
            clearance_ids: list of clearance GUIDs to be assigned
            start_time: the time the assignment should go into effect
            end_time: the time the assignment should expire

        Returns: the number of changes made
        """
        now = datetime.utcnow()
        if start_time or end_time:  # then add it to mongo
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

        if start_time is None:  # then add it in CCure
            new_assignments = []
            for assignee_id in assignee_ids:
                current_clearances = cls.get_clearances_by_assignee(assignee_id)
                current_clearance_guids = [clearance.id for clearance in current_clearances]
                for clearance_id in clearance_ids:
                    if clearance_id not in current_clearance_guids:
                        new_assignments.append({
                            "assignee_id": assignee_id,
                            "assigner_id": assigner_id,
                            "clearance_guid": clearance_id
                        })
            CcureApi.assign_clearances(new_assignments)

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
               clearance_ids: list[str]) -> int:
        """
        Revoke a list of clearances from a list of individuals

        Parameters:
            assigner_id: the campus ID of the person revoking clearances
            assignee_ids: list of campus IDs for people losing clearances
            clearance_ids: list of clearance GUIDs to be revoked

        Returns: the number of changes made
        """
        new_assignments = []
        for campus_id in assignee_ids:
            for clearance_id in clearance_ids:
                new_assignments.append({
                    "assignee_id": campus_id,
                    "assigner_id": assigner_id,
                    "clearance_id": clearance_id
                })
        CcureApi.revoke_clearances(new_assignments)

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
