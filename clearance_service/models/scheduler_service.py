"""Module containing SchedulerService, handling scheduled tasks"""

from datetime import datetime

import requests

from clearance_service.models.audit import Audit
from clearance_service.util.ccure_api import CcureApi
from clearance_service.util.db_connect import get_clearance_collection


class SchedulerService:
    """Class to handle tasks scheduled in the ServiceScheduler"""

    clearance_assignment = get_clearance_collection("clearance_assignment")

    @classmethod
    def get_clearance_assignments(cls) -> dict:
        """
        Get every clearance_assignment document that needs to be processed
        by the scheduler and group them by category. Includes:
            - indefinite_active_assignments: current active assignments
                without any stop date
            - temporary_active_assignments: current active assignments
                with a future stop date
            - expired_active_assignments: active assignments whose
                end dates have passed
            - revoked_assignments: documents revoking a clearance assignment

        Returns: a dict mapping document categories to lists of documents
        """
        now = datetime.utcnow()
        all_assignments = cls.clearance_assignment.aggregate(
            [
                {
                    "$facet": {
                        "indefinite_active_assignments": [
                            {
                                "$match": {
                                    "state": "assign-pending",
                                    "end_time": None,
                                    "$or": [
                                        {"start_time": None},
                                        {"start_time": {"$lte": now}},
                                    ],
                                }
                            },
                            {
                                "$project": {
                                    "assignee_id": 1,
                                    "assigner_id": 1,
                                    "clearance_id": 1,
                                    "message": "Activating clearance",
                                    "activate": "Y",
                                }
                            },
                        ],
                        "temporary_active_assignments": [
                            {
                                "$match": {
                                    "state": "assign-pending",
                                    "end_time": {"$gt": now},
                                    "$or": [{"start_time": None}, {"start_time": {"$lte": now}}],
                                }
                            },
                            {
                                "$project": {
                                    "assignee_id": 1,
                                    "assigner_id": 1,
                                    "clearance_id": 1,
                                    "message": "Activating clearance",
                                    "activate": "Y",
                                }
                            },
                        ],
                        "expired_active_assignments": [
                            {
                                "$match": {
                                    "state": {"$in": ["active", "assign-pending"]},
                                    "end_time": {"$lte": now},
                                }
                            },
                            {
                                "$project": {
                                    "assignee_id": 1,
                                    "assigner_id": 1,
                                    "clearance_id": 1,
                                    "message": "Clearance is expired.",
                                    "activate": "N",
                                }
                            },
                        ],
                        "revoked_assignments": [
                            {"$match": {"state": "revoke-pending"}},
                            {
                                "$project": {
                                    "assignee_id": 1,
                                    "assigner_id": 1,
                                    "clearance_id": 1,
                                    "submitted_time": 1,
                                    "message": "Revoking clearance",
                                    "activate": "N",
                                }
                            },
                        ],
                    }
                }
            ]
        )
        return next(all_assignments)

    @classmethod
    def push_to_ccure(cls):
        """
        An automated job that pushes new clearance assignments to CCure
        """
        assignments_by_category = cls.get_clearance_assignments()

        # delete clearance assignments that have been revoked
        for revoke_request in assignments_by_category["revoked_assignments"]:
            cls.clearance_assignment.delete_many(
                {
                    "state": {"$in": ["active", "assign-pending", "assign-pushed"]},
                    "assignee_id": revoke_request["assignee_id"],
                    "clearance_id": revoke_request["clearance_id"],
                    "submitted_time": {"$lte": revoke_request["submitted_time"]},
                }
            )

        new_assignments = []
        for category in assignments_by_category:
            for assignment in assignments_by_category[category]:
                new_assignments.append(
                    {
                        "assignee_id": assignment["assignee_id"],
                        "assigner_id": assignment["assigner_id"],
                        "clearance_guid": assignment["clearance_id"],
                        "message": assignment["message"],
                        "activate": assignment["activate"],
                    }
                )

        # temporary active and indefinite active get pushed to CCure
        CcureApi.assign_clearances([assg for assg in new_assignments if assg["activate"] == "Y"])
        # expired and revoked get pulled from CCure
        CcureApi.revoke_clearances([assg for assg in new_assignments if assg["activate"] == "N"])

        # audit the changes
        if new_assignments:
            now = datetime.utcnow()
            Audit.add_many(
                audit_configs=[
                    {
                        "assigner_id": new_assignment["assigner_id"],
                        "assignee_id": new_assignment["assignee_id"],
                        "clearance_id": new_assignment["clearance_guid"],
                        "clearance_name": CcureApi.get_clearance_name(
                            new_assignment["clearance_guid"]
                        ),
                        "timestamp": now,
                        "message": new_assignment["message"],
                    }
                    for new_assignment in new_assignments
                ]
            )

        # temporary assignments should have the state "active"
        active_ids = [doc["_id"] for doc in assignments_by_category["temporary_active_assignments"]]
        cls.clearance_assignment.update_many(
            {"_id": {"$in": active_ids}}, {"$set": {"state": "active"}}
        )
        # revoke requests should have the state "revoke-pushed"
        revoke_ids = [doc["_id"] for doc in assignments_by_category["revoked_assignments"]]
        cls.clearance_assignment.update_many(
            {"_id": {"$in": revoke_ids}}, {"$set": {"state": "revoke-pushed"}}
        )
        # all other assignments should have the state "assign-pushed", to be
        # processed by the daily delete_old_assignments job
        for category in ("indefinite_active_assignments", "expired_active_assignments"):
            ids = [doc["_id"] for doc in assignments_by_category[category]]
            cls.clearance_assignment.update_many(
                {"_id": {"$in": ids}}, {"$set": {"state": "assign-pushed"}}
            )

    @staticmethod
    def ccure_keepalive():
        """Keep the CCure api session active"""
        try:
            CcureApi.session_keepalive()
        except requests.ConnectTimeout:
            print("CCure timeout: Session keepalive call was not successful.")

    @classmethod
    def delete_old_assignments(cls):
        """
        A daily automated job that deletes old clearance assignments after
        the assignment has been pushed to CCure
        :returns None:
        """
        cls.clearance_assignment.delete_many({"state": {"$in": ["revoke-pushed", "assign-pushed"]}})
