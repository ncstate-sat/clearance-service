"""Tests for the audit endpoints"""

import bson
from auth_checker import AuthChecker
from fastapi.testclient import TestClient
from main import app
from pymongo import MongoClient

from clearance_service.tests.override_get_authorization import override_get_authorization
from clearance_service.util import db_connect
from clearance_service.util.authorization import get_authorization

client = TestClient(app)
app.dependency_overrides[get_authorization] = override_get_authorization


class TestAuditController:
    def mock_mongo_client(self, collection_name):
        """Mock a MongoDB database"""
        return MongoClient("mongodb://localhost:27017").clearance_service[collection_name]

    def test_search_actions(self, monkeypatch):
        """Tests the search_actions endpoint"""
        monkeypatch.setattr(db_connect, "get_clearance_collection", self.mock_mongo_client)
        monkeypatch.setattr(AuthChecker, "check_authorization", lambda *_, **__: None)

        ca_collection = self.mock_mongo_client("audit")

        audit_records = [
            {
                "_id": bson.ObjectId(),
                "assigner_id": "test_assigner",
                "assignee_id": "test_assignee",
                "clearance_id": None,
                "timestamp": 0,
                "message": "test_message",
            }
        ]

        ca_collection.insert_many(audit_records)

        response = client.get("/audit/", headers={"Authorization": "Bearer token"})

        assert response.status_code == 200

    def test_search_actions_by_assigner_pagination(self, monkeypatch):
        """Test the search_actions_by_assigner endpoint with pagination"""
        monkeypatch.setattr(db_connect, "get_clearance_collection", self.mock_mongo_client)
        monkeypatch.setattr(AuthChecker, "check_authorization", lambda *_, **__: None)

        ca_collection = self.mock_mongo_client("audit")

        audit_records = [
            {
                "_id": bson.ObjectId(),
                "assigner_id": "test_assigner",
                "assignee_id": "test_assignee",
                "clearance_id": None,
                "timestamp": 0,
                "message": "test_message",
            }
        ]

        ca_collection.insert_many(audit_records)

        response = client.get("/audit/?limit=1", headers={"Authorization": "Bearer token"})

        assert response.status_code == 200
