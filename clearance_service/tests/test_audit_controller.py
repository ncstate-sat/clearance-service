"""Tests for the audit endpoints"""
import bson
from fastapi.testclient import TestClient
from main import app

from clearance_service.tests.override_get_authorization import override_get_authorization
from clearance_service.util.authorization import get_authorization

client = TestClient(app)
app.dependency_overrides[get_authorization] = override_get_authorization


def test_search_actions(db, fake_auth):
    """Tests the search_actions endpoint"""

    ca_collection = db.audit

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
    assert db.audit.count_documents({}) == 1

    response = client.get("/audit/", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200


def test_search_actions_by_assigner_pagination(db, fake_auth):
    """Test the search_actions_by_assigner endpoint with pagination"""

    ca_collection = db.audit

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
