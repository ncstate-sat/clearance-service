"""
Tests for the assignments endpoints.
"""

import json
from fastapi import Response
from fastapi.testclient import TestClient
import requests
from pymongo import MongoClient
from deepdiff import DeepDiff
from main import app
from models.clearance_assignment import ClearanceAssignment
from util import db_connect
from util.auth_checker import AuthChecker
from util.ccure_api import CcureApi
from middleware.get_authorization import get_authorization
from tests.override_get_authorization import override_get_authorization


client = TestClient(app)
app.dependency_overrides[get_authorization] = override_get_authorization

clearances = [
    {
        "id": "DECBB54E-4B22-4671-9FA7-F8F370D66A97",
        "name": "Hunt - Turnstiles"
    },
    {
        "id": "E00D2258-4449-4ACD-B640-8163A4D6CAA2",
        "name": "Library - Faculty Commons"
    },
    {
        "id": "75A1AE65-798B-49DA-BDAC-671732AB4794",
        "name": "Library - Grad Commons"
    },
    {
        "id": "57685A64-A1DD-4F7D-8827-7D131F80B38D",
        "name": "VRB-SAT-Module 1 Contractor Access-C2"
    },
    {
        "id": "1FF93926-150D-42F5-8369-B755D9C17AEF",
        "name": "OIT-AFH-Building Exterior Automated-C2"
    }
]

assigned_clearances = [
    {
        "id": "DECBB54E-4B22-4671-9FA7-F8F370D66A97",
        "name": "Hunt - Turnstiles"
    },
    {
        "id": "E00D2258-4449-4ACD-B640-8163A4D6CAA2",
        "name": "Library - Faculty Commons"
    }
]


def mock_mongo_client(collection_name):
    """Mock a MongoDB database"""
    return MongoClient(
        "mongodb://localhost:27017").clearance_service[collection_name]


def mock_check_authorization(*_, **__):
    """"Mock AuthChecker response"""
    return None


def mock_get_assignments_by_assignee(*_, **__):
    """Mock ClearanceAssignment.get_assignments_by_assignee"""
    return [
        ClearanceAssignment(
            clearance_id="DECBB54E-4B22-4671-9FA7-F8F370D66A97"),
        ClearanceAssignment(
            clearance_id="E00D2258-4449-4ACD-B640-8163A4D6CAA2")
    ]


def mock_get_clearance_name(clearance_guid):
    """Mock getting a clearance name from a clearance ID"""
    for clearance in clearances:
        if clearance["id"] == clearance_guid:
            return clearance["name"]
    return ""


def mock_assign(_,
                assignee_ids: list[str],
                clearance_ids: list[str]):
    """Mock assigning a clearance"""
    return len(assignee_ids) * len(clearance_ids)


def mock_revoke(_,
                assignee_ids: list[str],
                clearance_ids: list[str]):
    """Mock reovking a clearance"""
    return len(assignee_ids) * len(clearance_ids)

def test_get_assignments(monkeypatch):
    """
    It should be able to get all active assignments for an individual.
    """
    monkeypatch.setattr(db_connect, "get_clearance_collection",
                        mock_mongo_client("clearance_assignment"))
    monkeypatch.setattr(AuthChecker, "check_authorization",
                        mock_check_authorization)
    monkeypatch.setattr(CcureApi, "get_clearance_name",
                        mock_get_clearance_name)
    monkeypatch.setattr(ClearanceAssignment, "get_assignments_by_assignee",
                        mock_get_assignments_by_assignee)

    response = client.get("/assignments/200103374",
                          headers={"Authorization": "Bearer token"})
    assert response.status_code == 200

    assert DeepDiff(response.json(), {
        "allowed": assigned_clearances,
        "assignments": assigned_clearances
    }, ignore_order=True) == {}


def test_assign_clearances(monkeypatch):
    """It should be able to assign clearances to an individual."""
    def mock_request_post(*_, **__):
        response = Response()
        response.headers = {"testing": True}
        #pylint: disable=protected-access
        response._content = json.dumps(
            {"data": {
                "successful": raw_assignees,
                "failed": []
            }}).encode("utf-8")
        return response

    monkeypatch.setattr(db_connect,
                        "get_clearance_collection",
                        mock_mongo_client("clearance_assignment"))
    monkeypatch.setattr(AuthChecker,
                        "check_authorization",
                        mock_check_authorization)
    monkeypatch.setattr(ClearanceAssignment, "assign", mock_assign)
    monkeypatch.setattr(requests, "post", mock_request_post)

    raw_assignees = [
        "200103374",
        "200103375"
    ]
    raw_clearance_ids = [
        "DECBB54E-4B22-4671-9FA7-F8F370D66A97",
        "75A1AE65-798B-49DA-BDAC-671732AB4794",
        "57685A64-A1DD-4F7D-8827-7D131F80B38D",
        "1FF93926-150D-42F5-8369-B755D9C17AEF"
    ]

    response = client.post("/assignments/assign",
                           headers={"Authorization": "Bearer token"},
                           json={
                               "assignees": raw_assignees,
                               "clearance_ids": raw_clearance_ids
                           })
    assert response.status_code == 200
    assert response.json() == {"changes": 8}


def test_revoke_clearances(monkeypatch):
    """It should be able to revoke clearances from an individual."""
    def mock_request_post(*_, **__):
        response = Response()
        response.headers = {"testing": True}
        #pylint: disable=protected-access
        response._content = json.dumps(
            {"data": {
                "successful": raw_assignees,
                "failed": []
            }}).encode("utf-8")
        return response

    monkeypatch.setattr(db_connect,
                        "get_clearance_collection",
                        mock_mongo_client("clearance_assignment"))
    monkeypatch.setattr(AuthChecker,
                        "check_authorization",
                        mock_check_authorization)
    monkeypatch.setattr(ClearanceAssignment, "revoke", mock_revoke)
    monkeypatch.setattr(requests, "post", mock_request_post)

    raw_assignees = [
        "200103374",
        "200103375"
    ]
    raw_clearance_ids = [
        "DECBB54E-4B22-4671-9FA7-F8F370D66A97",
        "75A1AE65-798B-49DA-BDAC-671732AB4794",
        "57685A64-A1DD-4F7D-8827-7D131F80B38D",
        "1FF93926-150D-42F5-8369-B755D9C17AEF"
    ]

    response = client.post("/assignments/revoke",
                           headers={"Authorization": "Bearer token"},
                           json={
                               "assignees": raw_assignees,
                               "clearance_ids": raw_clearance_ids
                           })
    assert response.status_code == 200
    assert response.json() == {"changes": 8}
