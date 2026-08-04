"""Tests for the audit endpoints"""
# using datetime module for test_search_actions_by_timeframe
from datetime import datetime, timedelta

# For URL encoding
from urllib.parse import quote

import bson
from fastapi.testclient import TestClient
from main import app

from clearance_service.tests.override_get_authorization import override_get_authorization_admin
from clearance_service.util.authorization import get_authorization

client = TestClient(app)
app.dependency_overrides[get_authorization] = override_get_authorization_admin


def test_search_actions(db, fake_auth):
    """Tests the search_actions endpoint"""

    ca_collection = db.audit

    audit_records = [
        {
            "_id": bson.ObjectId(),
            "assigner_name": "test_assigner",
            "assignee_name": "test_assignee",
            "assigner": "",
            "assignee": "",
            "action": "",
            "clearance_id": None,
            "clearance_name": "",
            "timestamp": datetime.now(),
            "message": "test_message",
        }
    ]

    ca_collection.insert_many(audit_records)
    assert db.audit.count_documents({}) == 1

    response = client.get("/audit", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert len(response.json()) == 1


def test_search_actions_with_null_names(db, fake_auth):
    """Records with null assigner_name/assignee_name (e.g. from before names were
    resolved, or an unmatched CCure lookup) should not break the endpoint"""

    ca_collection = db.audit

    audit_records = [
        {
            "_id": bson.ObjectId(),
            "assigner_name": None,
            "assignee_name": None,
            "assigner": "",
            "assignee": "",
            "action": "",
            "clearance_id": None,
            "clearance_name": "",
            "timestamp": datetime.now(),
            "message": "test_message",
        }
    ]

    ca_collection.insert_many(audit_records)

    response = client.get("/audit", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    records = response.json()["records"]
    assert len(records) == 1
    assert records[0]["assigner_name"] == ""
    assert records[0]["assignee_name"] == ""


def test_search_actions_by_assigner_pagination(db, fake_auth):
    """Test the search_actions_by_assigner endpoint with pagination"""

    ca_collection = db.audit

    audit_records = [
        {
            "_id": bson.ObjectId(),
            "assigner_name": "test_assigner",
            "assignee_name": "test_assignee",
            "clearance_id": None,
            "timestamp": datetime.now(),
            "message": "test_message",
            "assigner": "",
            "assignee": "",
            "action": "",
            "clearance_name": "",
        }
    ]

    ca_collection.insert_many(audit_records)

    response = client.get("/audit/?limit=1", headers={"Authorization": "Bearer token"})

    assert response.status_code == 200
    assert len(response.json()) == 1


def test_search_actions_by_timeframe(db, fake_auth):
    """Test the search_actions_by_test_by_timeframe"""

    ca_collection = db.audit

    audit_records = [
        {
            "_id": bson.ObjectId(),
            "assigner_name": "test_assigner",
            "assignee_name": "test_assignee",
            "clearance_id": None,
            "timestamp": datetime.now(),
            "message": "test_message",
            "assigner": "",
            "assignee": "",
            "action": "",
            "clearance_name": "",
        }
    ]

    ca_collection.insert_many(audit_records)

    timestamp = datetime.now()
    utc_timestamp = timestamp.astimezone()
    to_time = quote(utc_timestamp.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))

    earlier_time = timestamp - timedelta(minutes=5)
    utc_earlier_time = earlier_time.astimezone()
    from_time = quote(utc_earlier_time.strftime("%Y-%m-%dT%H:%M:%S.%fZ"))

    response = client.get(
        f"/audit/?limit=1&from_time={from_time}&to_time={to_time}",
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200
    assert len(response.json()) == 1
