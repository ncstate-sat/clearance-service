"""Tests for Validation Assignment controller"""

from datetime import datetime as dt
from datetime import timedelta

import bson
from pymongo import MongoClient

from clearance_service.models.audit import Audit
from clearance_service.models.scheduler_service import SchedulerService
from clearance_service.util import db_connect
from clearance_service.util.ccure_api import CcureApi


class TestSchedulerService:
    def mock_mongo_client(self, collection_name):
        """Mock a MongoDB database"""
        return MongoClient("mongodb://localhost:27017").clearance_service[collection_name]

    def test_delete_old_assignments(self, monkeypatch):
        """It should be able to delete old assignments."""

        monkeypatch.setattr(db_connect, "get_clearance_collection", self.mock_mongo_client)
        monkeypatch.setattr(
            SchedulerService, "clearance_assignment", self.mock_mongo_client("clearance_assignment")
        )

        old_assignments = [
            {
                "_id": bson.ObjectId(),
                "assigner_id": bson.ObjectId(),
                "assignee_id": bson.ObjectId(),
                "clearance_id": None,
                "state": "revoke-pushed",
                "start_time": 0,
                "end_time": dt.fromtimestamp(dt.now().timestamp() + 1000),
                "submitted_time": dt.now(),
            },
            {
                "_id": bson.ObjectId(),
                "assigner_id": bson.ObjectId(),
                "assignee_id": bson.ObjectId(),
                "clearance_id": None,
                "state": "assign-pushed",
                "start_time": 0,
                "end_time": dt.fromtimestamp(dt.now().timestamp() - 1000),
                "submitted_time": dt.now(),
            },
            {
                "_id": bson.ObjectId(),
                "assigner_id": bson.ObjectId(),
                "assignee_id": bson.ObjectId(),
                "clearance_id": None,
                "state": "active",
                "start_time": 0,
                "end_time": dt.fromtimestamp(dt.now().timestamp() - 1000),
                "submitted_time": dt.now(),
            },
        ]

        db_connect.get_clearance_collection("clearance_assignment").insert_many(old_assignments)

        SchedulerService.delete_old_assignments()

        assert db_connect.get_clearance_collection("clearance_assignment").count_documents({}) == 1

        monkeypatch.undo()

    def test_get_all_clearance_assignments(self, monkeypatch):
        """It should be able to get all clearance assignments."""

        monkeypatch.setattr(db_connect, "get_clearance_collection", self.mock_mongo_client)
        monkeypatch.setattr(
            SchedulerService, "clearance_assignment", self.mock_mongo_client("clearance_assignment")
        )

        assignments = [
            {
                # indefinite active
                "assignee_id": bson.ObjectId(),
                "assigner_id": bson.ObjectId(),
                "clearance_id": bson.ObjectId(),
                "state": "assign-pending",
                "start_time": None,
                "end_time": None,
                "submitted_time": dt.now().timestamp(),
            },
            {
                # indefinite active
                "assignee_id": bson.ObjectId(),
                "assigner_id": bson.ObjectId(),
                "clearance_id": bson.ObjectId(),
                "state": "assign-pending",
                "start_time": dt(2000, 1, 1),
                "end_time": None,
                "submitted_time": dt.now().timestamp(),
            },
            {
                # temporary active
                "assignee_id": bson.ObjectId(),
                "assigner_id": bson.ObjectId(),
                "clearance_id": bson.ObjectId(),
                "state": "assign-pending",
                "start_time": None,
                "end_time": dt.now() + timedelta(days=10),
                "submitted_time": dt.now().timestamp(),
            },
            {
                # expired active
                "assignee_id": bson.ObjectId(),
                "assigner_id": bson.ObjectId(),
                "clearance_id": bson.ObjectId(),
                "state": "active",
                "start_time": None,
                "end_time": dt(2020, 4, 20),
                "submitted_time": dt.now().timestamp(),
            },
            {
                # expired active
                "assignee_id": bson.ObjectId(),
                "assigner_id": bson.ObjectId(),
                "clearance_id": bson.ObjectId(),
                "state": "assign-pending",
                "start_time": None,
                "end_time": dt(1955, 2, 14),
                "submitted_time": dt.now().timestamp(),
            },
            {
                # revoked
                "assignee_id": bson.ObjectId(),
                "assigner_id": bson.ObjectId(),
                "clearance_id": bson.ObjectId(),
                "state": "revoke-pending",
                "start_time": None,
                "end_time": None,
                "submitted_time": dt.now().timestamp(),
            },
            {
                # revoked
                "assignee_id": bson.ObjectId(),
                "assigner_id": bson.ObjectId(),
                "clearance_id": bson.ObjectId(),
                "state": "revoke-pending",
                "start_time": None,
                "end_time": None,
                "submitted_time": dt.now().timestamp(),
            },
            {
                # revoked
                "assignee_id": bson.ObjectId(),
                "assigner_id": bson.ObjectId(),
                "clearance_id": bson.ObjectId(),
                "state": "revoke-pending",
                "start_time": None,
                "end_time": None,
                "submitted_time": dt.now().timestamp(),
            },
            {
                # none. don't process.
                "assignee_id": bson.ObjectId(),
                "assigner_id": bson.ObjectId(),
                "clearance_id": bson.ObjectId(),
                "state": "revoke-pending",
                "start_time": dt.now() + timedelta(days=10),
                "end_time": None,
                "submitted_time": dt.now().timestamp(),
            },
        ]

        db_connect.get_clearance_collection("clearance_assignment").insert_many(assignments)

        results = SchedulerService.get_clearance_assignments()
        assert "indefinite_active_assignments" in results
        assert "temporary_active_assignments" in results
        assert "expired_active_assignments" in results
        assert "revoked_assignments" in results

        assert len(results["indefinite_active_assignments"]) == 2
        assert len(results["temporary_active_assignments"]) == 1
        assert len(results["expired_active_assignments"]) == 2
        assert len(results["revoked_assignments"]) == 4

        monkeypatch.undo()

    def test_future_active_clearance_assignments(self, monkeypatch):
        """
        It should not push Clearance Assignments that are 'assign-pending'
        and have a start_time in the future.
        """

        monkeypatch.setattr(db_connect, "get_clearance_collection", self.mock_mongo_client)
        monkeypatch.setattr(
            SchedulerService, "clearance_assignment", self.mock_mongo_client("clearance_assignment")
        )

        assignment = {
            "_id": bson.ObjectId(),
            "assigner_id": bson.ObjectId(),
            "assignee_id": bson.ObjectId(),
            "clearance_id": bson.ObjectId(),
            "state": "assign-pending",
            "start_time": dt.now() + timedelta(days=10),
            "end_time": 0,
            "submitted_time": 0,
        }

        db_connect.get_clearance_collection("clearance_assignment").insert_one(assignment)

        results = SchedulerService.get_clearance_assignments()
        assert "indefinite_active_assignments" in results
        assert "temporary_active_assignments" in results
        assert "expired_active_assignments" in results
        assert "revoked_assignments" in results

        assert len(results["indefinite_active_assignments"]) == 0
        assert len(results["temporary_active_assignments"]) == 0
        assert len(results["expired_active_assignments"]) == 0
        assert len(results["revoked_assignments"]) == 0

        monkeypatch.undo()

    def test_temporary_assignments(self, monkeypatch):
        """
        It should push to CCure, create a document in the audit collection,
        and update the state to "active" for clearance assignments that are
        'assign-pending', not before start date, and a future end date
        """

        monkeypatch.setattr(db_connect, "get_clearance_collection", self.mock_mongo_client)
        monkeypatch.setattr(
            SchedulerService, "clearance_assignment", self.mock_mongo_client("clearance_assignment")
        )
        monkeypatch.setattr(Audit, "collection", self.mock_mongo_client("audit"))
        monkeypatch.setattr(CcureApi, "assign_clearances", lambda *_, **__: None)
        monkeypatch.setattr(CcureApi, "revoke_clearances", lambda *_, **__: None)
        monkeypatch.setattr(CcureApi, "get_person_by_campus_id", lambda *_, **__: {})
        monkeypatch.setattr(CcureApi, "get_clearance_by_guid", lambda *_, **__: {})

        assignment = {
            "_id": bson.ObjectId(),
            "assignee_id": bson.ObjectId(),
            "assigner_id": bson.ObjectId(),
            "clearance_id": bson.ObjectId(),
            "state": "assign-pending",
            "start_time": None,
            "end_time": dt.now() + timedelta(days=10),
            "submitted_time": dt.now().timestamp(),
        }

        db_connect.get_clearance_collection("clearance_assignment").insert_one(assignment)

        # test that the new assignment is categorized correctly
        results = SchedulerService.get_clearance_assignments()
        assert "indefinite_active_assignments" in results
        assert "temporary_active_assignments" in results
        assert "expired_active_assignments" in results
        assert "revoked_assignments" in results

        assert len(results["indefinite_active_assignments"]) == 0
        assert len(results["temporary_active_assignments"]) == 1
        assert len(results["expired_active_assignments"]) == 0
        assert len(results["revoked_assignments"]) == 0

        SchedulerService.push_to_ccure()

        # test that the state has changed and the assignment has been audited
        audit_result = db_connect.get_clearance_collection("audit").find_one({})
        assert audit_result is not None

        new_ca_record = db_connect.get_clearance_collection("clearance_assignment").find_one({})
        assert new_ca_record.get("state") == "active"

        monkeypatch.undo()
