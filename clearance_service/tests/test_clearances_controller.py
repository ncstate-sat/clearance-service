"""Tests for the clearance endpoints"""

from auth_checker import AuthChecker
from fastapi.testclient import TestClient
from main import app
from pymongo import MongoClient

from clearance_service.models.clearance import Clearance
from clearance_service.tests.override_get_authorization import (
    override_get_authorization,
    override_get_authorization_liaison,
)
from clearance_service.util import db_connect
from clearance_service.util.authorization import get_authorization
from clearance_service.util.ccure_api import CcureApi

client = TestClient(app)

# Clearance data returned from CCure api
clearances_response = [
    {
        "_id": "00BC9D72-F88C-4763-92B4-C41B946827A4",
        "ccure_id": 5000,
        "clearance_name": "VRB-SAT-Module 1 B140 Software Developer-C2",
    },
    {
        "_id": "2C124A2A-5C4E-4B96-B0B2-D688CCB8CA6B",
        "ccure_id": 5001,
        "clearance_name": "VRB - Module 2 Student Suite",
    },
    {
        "_id": "3CD319E4-4718-4605-8505-C7E3848AE01F",
        "ccure_id": 5002,
        "clearance_name": "VRB - Module 2 - 1007 Wet Lab",
    },
    {
        "_id": "41C69822-9E33-4F8C-AE0B-DD77272A5867",
        "ccure_id": 5003,
        "clearance_name": "VRB - Module 6 & 7 All Common Doors",
    },
    {
        "_id": "44BD86BC-A075-4E65-B66C-7F680DABBBDA",
        "ccure_id": 5004,
        "clearance_name": "VRB - Module 6 - 1543 Lab",
    },
]

# Clearance IDs allowed for liaison
allowed_liaison_clearances = [
    "00BC9D72-F88C-4763-92B4-C41B946827A4",
    "2C124A2A-5C4E-4B96-B0B2-D688CCB8CA6B",
]

clean_clearances_full = []  # Clearances for admins
clean_clearances_partial = []  # Clearances for liaisons
for clearance in clearances_response:
    new_clearance = {
        "id": clearance["_id"],
        "ccure_id": clearance["ccure_id"],
        "name": clearance["clearance_name"],
    }
    clean_clearances_full.append(new_clearance)
    if new_clearance["id"] in allowed_liaison_clearances:
        clean_clearances_partial.append(new_clearance)


def mock_mongo_client():
    """Mock a MongoDB database"""
    return MongoClient("mongodb://localhost:27017").db


def mock_check_authorization(*_, **__):
    """ "Mock AuthChecker response"""
    return None


def mock_get_clearances(*_, **__):
    """Mock the CCure endpoint to get clearances"""
    return clearances_response


def mock_clearance_get(*_, **__):
    """Mock the Clearance.get method"""
    return [
        Clearance(item["_id"], item["ccure_id"], item["clearance_name"])
        for item in clearances_response
    ]


def mock_get_clearance_name(clearance_guid):
    """Mock getting a clearance name from a clearance ID"""
    for clnce in clean_clearances_full:
        if clnce["id"] == clearance_guid:
            return clnce["name"]
    return ""


def mock_get_allowed(*_, **__):
    """Mock getting clearances for liaisons"""
    return [
        {
            "id": "00BC9D72-F88C-4763-92B4-C41B946827A4",
            "ccure_id": 5000,
            "name": "VRB-SAT-Module 1 B140 Software Developer-C2",
        },
        {
            "id": "2C124A2A-5C4E-4B96-B0B2-D688CCB8CA6B",
            "ccure_id": 5001,
            "name": "VRB - Module 2 Student Suite",
        },
    ]


def test_get_clearances_as_admin(monkeypatch):
    """
    It should be able to search for clearances as an admin and get a
    full list returned.
    """
    app.dependency_overrides[get_authorization] = override_get_authorization

    monkeypatch.setattr(AuthChecker, "check_authorization", mock_check_authorization)
    monkeypatch.setattr(db_connect, "get_clearance_collection", mock_mongo_client)
    monkeypatch.setattr(CcureApi, "get_clearance_name", mock_get_clearance_name)
    monkeypatch.setattr(Clearance, "get", mock_clearance_get)

    search_query = "VRB"
    response = client.get(
        f"/clearances?search={search_query}", headers={"Authorization": "Bearer token"}
    )
    assert response.status_code == 200
    assert response.json() == {"clearance_names": clean_clearances_full}


def test_get_clearances_as_liaison(monkeypatch):
    """
    It should be able to search for clearances as a liaison and get a
    partial list with only the allowed clearances.
    """
    app.dependency_overrides[get_authorization] = override_get_authorization_liaison

    monkeypatch.setattr(AuthChecker, "check_authorization", mock_check_authorization)
    monkeypatch.setattr(db_connect, "get_clearance_collection", mock_mongo_client)
    monkeypatch.setattr(CcureApi, "get_clearance_name", mock_get_clearance_name)
    monkeypatch.setattr(Clearance, "get", mock_clearance_get)
    monkeypatch.setattr(Clearance, "get_allowed", mock_get_allowed)

    search_query = "VRB"
    response = client.get(
        f"/clearances?search={search_query}", headers={"Authorization": "Bearer token"}
    )
    assert response.status_code == 200
    assert response.json() == {"clearance_names": clean_clearances_partial}
