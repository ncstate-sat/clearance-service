"""Model for Clearance Assignments"""

from typing import Optional
from datetime import datetime, date
from fastapi import status
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
        self.clearance = Clearance(_id=clearance_id, name=clearance_name)
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
        assignee_object_id = CcureApi.get_person_object_id(assignee_id)
        assigned_clearances = CcureApi.get_assigned_clearances(assignee_object_id)
        if assigned_clearances.status_code == status.HTTP_404_NOT_FOUND:
            return []
        clearance_ids = [pair.get("ClearanceID") for pair in assigned_clearances.json()]
        if not clearance_ids:
            return []

        # then get the guids for those clearances
        assigned_clearances = CcureApi.get_clearances_by_id(clearance_ids)
        return [Clearance(
            clearance.get("GUID"),
            clearance.get("ObjectID"),
            clearance.get("Name")
        ) for clearance in assigned_clearances]

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
               assigner_email: str,
               assignee_ids: list[str],
               clearance_guids: list[str],
               start_time: Optional[date] = None,
               end_time: Optional[date] = None) -> int:
        """
        Assign a list of clearances to a list of individuals

        Parameters:
            assigner_email: the email address of the person assigning clearances
            assignee_ids: list of campus IDs for people getting clearances
            clearance_guids: list of clearance GUIDs to be assigned
            start_time: the time the assignment should go into effect
            end_time: the time the assignment should expire

        Returns: the number of changes made
        """
        now = datetime.utcnow()
        assigner_id = CcureApi.get_campus_id_by_email(assigner_email)
        if start_time or end_time:  # then add it to mongo
            new_assignments = []
            for assignee_id in assignee_ids:
                for clearance_id in clearance_guids:
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
                current_clearance_guids = [clearance.id
                                           for clearance in current_clearances]
                for clearance_id in clearance_guids:
                    if clearance_id not in current_clearance_guids:
                        new_assignments.append({
                            "assignee_id": assignee_id,
                            "assigner_id": assigner_id,
                            "clearance_guid": clearance_id
                        })
            clearances_data = CcureApi.assign_clearances(new_assignments)

            # audit the new assignment
            Audit.add_many(audit_configs=[{
                "assigner_id": new_assignment["assigner_id"],
                "assignee_id": new_assignment["assignee_id"],
                "clearance_id": new_assignment["clearance_guid"],
                "clearance_name": clearances_data[
                    new_assignment["clearance_guid"]]["name"],
                "timestamp": now,
                "message": "Activating clearance"
            } for new_assignment in new_assignments])

        return len(assignee_ids) * len(clearance_guids)

    @staticmethod
    def revoke(assigner_email: str,
               assignee_ids: list[str],
               clearance_ids: list[str]) -> int:
        """
        Revoke a list of clearances from a list of individuals

        Parameters:
            assigner_email: the email address of the person revoking clearances
            assignee_ids: list of campus IDs for people losing clearances
            clearance_ids: list of clearance GUIDs to be revoked

        Returns: the number of changes made
        """
        assigner_id = CcureApi.get_campus_id_by_email(assigner_email)
        new_assignments = []
        for campus_id in assignee_ids:
            for clearance_id in clearance_ids:
                new_assignments.append({
                    "assignee_id": campus_id,
                    "assigner_id": assigner_id,
                    "clearance_guid": clearance_id
                })
        clearances_data = CcureApi.revoke_clearances(new_assignments)

        # audit the new revocation
        now = datetime.utcnow()
        Audit.add_many(audit_configs=[{
            "assigner_id": new_assignment["assigner_id"],
            "assignee_id": new_assignment["assignee_id"],
            "clearance_id": new_assignment["clearance_guid"],
            "clearance_name": clearances_data[
                new_assignment["clearance_guid"]]["name"],
            "timestamp": now,
            "message": "Revoking clearance"
        } for new_assignment in new_assignments])
        return len(assignee_ids) * len(clearance_ids)
