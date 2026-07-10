"""Tests for the clearance endpoints"""

from fastapi.testclient import TestClient
from main import app

from clearance_service.models import acs
from clearance_service.models.clearance import Clearance
from clearance_service.tests.override_get_authorization import (
    override_get_authorization_admin,
    override_get_authorization_liaison,
)
from clearance_service.util.authorization import get_authorization
from clearance_service.util.handle_requests import RequestException

client = TestClient(app)

# Clearance data returned from acslib
clearances_response = [
    {
        "_id": 5000,
        "clearance_name": "VRB-SAT-Module 1 B140 Software Developer-C2",
    },
    {
        "_id": 5001,
        "clearance_name": "VRB - Module 2 Student Suite",
    },
    {
        "_id": 5002,
        "clearance_name": "VRB - Module 2 - 1007 Wet Lab",
    },
    {
        "_id": 5003,
        "clearance_name": "VRB - Module 6 & 7 All Common Doors",
    },
    {
        "_id": 5004,
        "clearance_name": "VRB - Module 6 - 1543 Lab",
    },
]

# Clearance IDs allowed for liaison
allowed_liaison_clearances = [5000, 5001]

clean_clearances_full = []  # Clearances for admins
clean_clearances_partial = []  # Clearances for liaisons
for clearance in clearances_response:
    new_clearance = {
        "id": clearance["_id"],
        "name": clearance["clearance_name"],
    }
    clean_clearances_full.append(new_clearance)
    if new_clearance["id"] in allowed_liaison_clearances:
        clean_clearances_partial.append(new_clearance)


def mock_clearance_get(*_, **__):
    """Mock the Clearance.get method"""
    return [Clearance(item["_id"], item["clearance_name"]) for item in clearances_response]


def mock_get_clearance_name(clearance_id):
    """Mock getting a clearance name from a clearance ID"""
    for clnce in clean_clearances_full:
        if clnce["id"] == clearance_id:
            return clnce["name"]
    return ""


def mock_get_allowed(*_, **__):
    """Mock getting clearances for liaisons"""
    return [
        {
            "id": 5000,
            "name": "VRB-SAT-Module 1 B140 Software Developer-C2",
        },
        {
            "id": 5001,
            "name": "VRB - Module 2 Student Suite",
        },
    ]


def mock_error(*_, **__):
    """Mock Request Exception"""
    raise RequestException(400, "Bad request")


def test_error_get_clearances(db, fake_auth, monkeypatch):
    """
    It should be able to search for clearances as an admin and get a
    full list returned.
    """
    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    monkeypatch.setattr(acs.clearance, "get_property", mock_get_clearance_name)
    monkeypatch.setattr(Clearance, "get", mock_error)

    search_query = "VRB"
    response = client.get(
        f"/clearances?search={search_query}", headers={"Authorization": "Bearer token"}
    )
    assert response.status_code == 400


def test_get_clearances_as_admin(db, fake_auth, monkeypatch):
    """
    It should be able to search for clearances as an admin and get a
    full list returned.
    """
    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    monkeypatch.setattr(acs.clearance, "get_property", mock_get_clearance_name)
    monkeypatch.setattr(Clearance, "get", mock_clearance_get)

    search_query = "VRB"
    response = client.get(
        f"/clearances?search={search_query}", headers={"Authorization": "Bearer token"}
    )
    assert response.status_code == 200
    assert response.json() == {"clearance_names": clean_clearances_full}


def test_get_clearances_as_liaison(db, fake_auth, monkeypatch):
    """
    It should be able to search for clearances as a liaison and get a
    partial list with only the allowed clearances.
    """
    app.dependency_overrides[get_authorization] = override_get_authorization_liaison

    monkeypatch.setattr(acs.clearance, "get_property", mock_get_clearance_name)
    monkeypatch.setattr(Clearance, "get", mock_clearance_get)
    monkeypatch.setattr(Clearance, "get_allowed", mock_get_allowed)

    search_query = "VRB"
    response = client.get(
        f"/clearances?search={search_query}", headers={"Authorization": "Bearer token"}
    )
    assert response.status_code == 200
    assert response.json() == {"clearance_names": clean_clearances_partial}


def test_get_clearances_as_liaison_with_special_chars(db, fake_auth, monkeypatch):
    """
    It should be able to search for clearances as a liaison, handling special characters, and get a
    partial list with only the allowed clearances.
    """
    app.dependency_overrides[get_authorization] = override_get_authorization_liaison

    monkeypatch.setattr(acs.clearance, "get_property", mock_get_clearance_name)
    monkeypatch.setattr(Clearance, "get", mock_clearance_get)
    monkeypatch.setattr(Clearance, "get_allowed", mock_get_allowed)

    search_query = "*vr(b]."
    response = client.get(
        f"/clearances?search={search_query}", headers={"Authorization": "Bearer token"}
    )
    assert response.status_code == 200
    assert response.json() == {"clearance_names": clean_clearances_partial}
