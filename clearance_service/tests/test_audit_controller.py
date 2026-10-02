"""Tests for the audit endpoints"""
# using datetime module for test_search_actions_by_timeframe
from datetime import datetime, timedelta

# For URL encoding
from urllib.parse import quote

import bson
from fastapi.testclient import TestClient
from main import app

from clearance_service.models import acs
from clearance_service.models.audit import Audit
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
    assert records[0]["assigner_email"] == ""
    assert records[0]["assignee_email"] == ""


def test_search_actions_includes_emails(db, fake_auth):
    """Emails are returned so a client can identify people whose names aren't known"""
    db.audit.insert_one(
        {
            "assigner_name": "Assigner Person",
            "assigner_email": "assigner@email.com",
            "assignee_name": "",
            "assignee_email": "assignee@email.com",
            "action": "ClearanceA revoked",
            "clearance_id": 1234,
            "clearance_name": "ClearanceA",
            "timestamp": datetime.now(),
        }
    )

    response = client.get("/audit", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    record = response.json()["records"][0]
    assert record["assigner_email"] == "assigner@email.com"
    assert record["assignee_name"] == ""
    assert record["assignee_email"] == "assignee@email.com"


def test_add_many_resolves_names(db, monkeypatch):
    """Names come from CCure's ProperName, matching emails case-insensitively,
    and fall back to empty when the person isn't found in CCure"""
    search_filters = []

    def mock_personnel_search(_terms, search_filter, *_, **__):
        search_filters.append(search_filter)
        return [
            {"ProperName": "Pat Smith", "EmailAddress": "PSmith@email.com"},
            {"ProperName": "Sam Jones", "EmailAddress": "sjones@email.com"},
        ]

    monkeypatch.setattr(Audit, "collection", db.audit)
    monkeypatch.setattr(acs.personnel, "search", mock_personnel_search)

    Audit.add_many(
        [
            Audit.NewAuditData(
                assigner_email="sjones@email.com",
                assigner_name="token name",
                assignee_email=assignee_email,
                clearance_id=1234,
                clearance_name="ClearanceA",
                message_base=" revoked",
            )
            for assignee_email in ["psmith@email.com", "unknown@email.com"]
        ]
    )

    records = {r["assignee_email"]: r for r in db.audit.find()}
    assert records["psmith@email.com"]["assignee_name"] == "Pat Smith"
    assert records["psmith@email.com"]["assigner_name"] == "Sam Jones"
    assert records["unknown@email.com"]["assignee_name"] == ""
    # CCure only returns ProperName when it's in the explicit property list
    assert "ProperName" in search_filters[0].explicit_property_list


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
