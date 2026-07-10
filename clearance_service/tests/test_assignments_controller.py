"""
Tests for the assignments endpoints.
"""

import json
from datetime import datetime, timedelta, timezone

import requests
from acslib.ccure.crud import CcureClearance, CcurePersonnel
from fastapi import Response
from fastapi.testclient import TestClient
from main import app

from clearance_service.models import acs
from clearance_service.models.audit import Audit
from clearance_service.models.clearance import Clearance
from clearance_service.models.personnel import Personnel
from clearance_service.models.scheduled_action import ScheduledAction
from clearance_service.tests.override_get_authorization import (
    override_get_authorization_admin,
    override_get_authorization_liaison,
)
from clearance_service.util.authorization import get_authorization
from clearance_service.util.handle_requests import RequestException
from clearance_service.util.settings import C9K_CLEARANCE_LIMIT

client = TestClient(app)
app.dependency_overrides[get_authorization] = override_get_authorization_admin

clearances = [
    {"id": 5000, "name": "Hunt - Turnstiles"},
    {"id": 5001, "name": "Library - Faculty Commons"},
    {"id": 5002, "name": "Library - Grad Commons"},
    {"id": 5003, "name": "VRB-SAT-Module 1 Contractor Access-C2"},
    {"id": 5004, "name": "OIT-AFH-Building Exterior Automated-C2"},
]

assigned_clearances = [
    {"id": 5000, "name": "Hunt - Turnstiles", "can_revoke": True},
    {
        "id": 5001,
        "name": "Library - Faculty Commons",
        "can_revoke": False,
    },
]


class FakeResponse:
    def __init__(self):
        self.status_code = 200
        self.json = lambda: {}
        self.headers = {}


def mock_request_post(raw_assignees: list[str], *_, **__):
    response = Response()
    response.headers = {"testing": True}
    # pylint: disable=protected-access
    response._content = json.dumps({"data": {"successful": raw_assignees, "failed": []}}).encode(
        "utf-8"
    )
    return response


def mock_get_clearances_by_assignee(assignee_email, *_, **__):
    """Mock ClearanceAssignment.get_clearances_by_assignee"""
    if assignee_email == "person2@gmail.com":
        return []
    return [
        Clearance(_id=5000),
        Clearance(_id=5001),
    ]


def mock_get_clearance_name(clearance_id, _):
    """Mock getting a clearance name from a clearance ID"""
    for clearance in clearances:
        if clearance["id"] == clearance_id:
            return clearance["name"]
    return ""


def mock_process(configs: list[ScheduledAction.ActionConfig], **kwargs):
    """Mock assigning a clearance"""
    succeeded_actions = {}
    for config in configs:
        assignee_email = config.assignee_email or None
        clearance_id = config.clearance_id or None

        if succeeded_actions.get(assignee_email) is None:
            succeeded_actions[assignee_email] = {}
        succeeded_actions[assignee_email][clearance_id] = True
    return {"succeeded": succeeded_actions, "failed": {}, "pending": []}


def mock_get_audit_log(**kwargs):
    """Mock Audit.get_audit_log"""
    return [
        Audit(
            audit_data=Audit.AuditRecord(
                assigner_name="test assigner",
                assignee_name="test assignee",
                action="some clearance assigned.",
                timestamp=datetime.now(),
            )
        )
    ]


def mock_acs_personnel_search(*args, **kwargs):
    """Mock acslib people search"""
    return [
        {
            "ProperName": "John Champion",
            "ObjectID": 5001,
            "LastName": "Champion",
            "FirstName": "John",
            "MiddleName": "",
            "EmailAddress": "person1@email.com",
            "Disabled": False,
        },
        {
            "ProperName": "John Champion",
            "ObjectID": 6001,
            "LastName": "Champion",
            "FirstName": "John",
            "MiddleName": "",
            "EmailAddress": "person2@email.com",
            "Disabled": False,
        },
        {
            "ProperName": "Ryan Semmler",
            "ObjectID": 7001,
            "LastName": "Semmler",
            "FirstName": "Ryan",
            "MiddleName": "",
            "EmailAddress": "person3@email.com",
            "Disabled": False,
        },
    ]


def mock_acs_clearance_search(*args, **kwargs):
    """Mock acslib clearance search"""
    return [
        {
            "*state": 1,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.Clearance",
            "GUID": "2c124a2a-5c4e-4b96-b0b2-d688ccb8ca6b",
            "ObjectID": 5000,
            "Name": "VRB-01-1002-Module 2 Student Suite-DEPT",
            "*appServer": "VRB-C9K-02",
            "*PK": ["ObjectID"],
        },
        {
            "*state": 1,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.Clearance",
            "GUID": "2c124a2a-5c4e-4b96-b0b2-d688ccb8ca6b",
            "ObjectID": 5002,
            "Name": "VRB-01-1002-Module 2 Student Suite-DEPT",
            "*appServer": "VRB-C9K-02",
            "*PK": ["ObjectID"],
        },
        {
            "*state": 1,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.Clearance",
            "GUID": "2c124a2a-5c4e-4b96-b0b2-d688ccb8ca6b",
            "ObjectID": 5003,
            "Name": "VRB-01-1002-Module 2 Student Suite-DEPT",
            "*appServer": "VRB-C9K-02",
            "*PK": ["ObjectID"],
        },
        {
            "*state": 1,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.Clearance",
            "GUID": "2c124a2a-5c4e-4b96-b0b2-d688ccb8ca6b",
            "ObjectID": 5004,
            "Name": "VRB-01-1002-Module 2 Student Suite-DEPT",
            "*appServer": "VRB-C9K-02",
            "*PK": ["ObjectID"],
        },
    ]


def mock_get_clearance_items(*_, **__):
    return [
        {
            "*state": 1,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.ClearanceItem",
            "GUID": "9c3bd102-a49f-4b8f-b9fa-03e483f97a3f",
            "ClearanceID": 5000,
            "DoorID": 3000,
            "ElevatorID": None,
            "ScheduleID": 2,
            "DoorGroupID": None,
            "ElevatorGroupID": None,
            "*appServer": "VRB-C9K-02",
            "ObjectID": 5003,
            "*PK": ["ObjectID"],
        },
        {
            "*state": 1,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.ClearanceItem",
            "GUID": "c2973f52-13fa-441c-a6fb-6acbeace3585",
            "ClearanceID": 5000,
            "DoorID": 3001,
            "ElevatorID": None,
            "ScheduleID": 3,
            "DoorGroupID": None,
            "ElevatorGroupID": None,
            "*appServer": "VRB-C9K-02",
            "ObjectID": 5004,
            "*PK": ["ObjectID"],
        },
    ]


def mock_get_acs_doors(*_, **__):
    """Mock getting ACS doors."""
    return [
        {
            "*state": 1,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
            "GUID": "95ea96cd-612a-45e3-8d54-f0ffb7a43f8a",
            "ObjectID": 3000,
            "Name": "VRB-B-B103C-Test Door 1234",
            "ControllerClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarController",
            "MaintenanceMode": False,
            "RequireManualActionInstructions": False,
            "ModeStatus": 2,
            "OpenStatus": 2,
            "AlarmStateStatus": 1,
            "*appServer": "VRB-C9K-02",
            "*PK": ["ObjectID"],
        },
        {
            "*state": 1,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
            "GUID": "79652106-64bf-4bc0-a20d-6104d6e57a7d",
            "ObjectID": 3001,
            "Name": "VRB-B-B103C-Test Door 5678",
            "ControllerClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarController",
            "MaintenanceMode": False,
            "RequireManualActionInstructions": False,
            "ModeStatus": 2,
            "OpenStatus": 2,
            "AlarmStateStatus": 1,
            "*appServer": "VRB-C9K-02",
            "*PK": ["ObjectID"],
        },
    ]


def mock_assign_clearances(*_, **__):
    """Mock a clearance assignment in acs."""
    return


def mock_get_assigned_clearances(*_, **__):
    """Mock returning clearances for a person"""
    return []


def mock_find_by_email(*_, **__):
    """Mock Personnel.search_by_email"""
    return [
        Personnel({
            "FirstName": "John",
            "MiddleName": None,
            "LastName": "Champion",
            "EmailAddress": "person2@email.com",
            "ObjectID": 5001,
        }),
    ]


def mock_get_allowed(*_, **__):
    """Mock Clearance.get_allowed"""
    return [
        Clearance(5000, name="Clearance1"),
        Clearance(5002, name="Clearance2"),
    ]


def mock_get_clearances_by_assignee_clearance_limit(*_, **__):
    """
    Mock ClearanceAssignment.get_clearances_by_assignee
    Return a list of clearances just under the assignment limit
    """
    return [Clearance(i, f"fake clearance {i}") for i in range(C9K_CLEARANCE_LIMIT - 2)]


def mock_error(*_, **__):
    """Mock Request Exception"""
    raise RequestException(400, "Bad request")


def test_error_get_assignments(db, fake_auth, monkeypatch):
    """
    It should be able to catch the error thrown by mock function.
    """
    monkeypatch.setattr(acs.clearance, "get_property", mock_get_clearance_name)
    monkeypatch.setattr(ScheduledAction, "get_clearances_by_assignee", mock_error)

    response = client.get("/assignments/person2@email.com", headers={"Authorization": "Bearer token"})
    assert response.status_code == 400


def test_get_assignments_as_admin(db, fake_auth, monkeypatch):
    """
    It should be able to get all active assignments for an individual.
    """
    monkeypatch.setattr(acs.clearance, "get_property", mock_get_clearance_name)
    monkeypatch.setattr(
        ScheduledAction, "get_clearances_by_assignee", mock_get_clearances_by_assignee
    )
    response = client.get("/assignments/person2@email.com", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json() == {
        "assignments": [
            {
                "id": 5000,
                "name": "Hunt - Turnstiles",
                "can_revoke": True,
            },
            {
                "id": 5001,
                "name": "Library - Faculty Commons",
                "can_revoke": True,
            },
        ]
    }


def test_get_assignments_with_doors(db, fake_auth, monkeypatch):
    """
    It should be able to get all active assignments and their doors for an individual.
    """
    monkeypatch.setattr(acs.clearance, "get_property", mock_get_clearance_name)
    monkeypatch.setattr(
        ScheduledAction, "get_clearances_by_assignee", mock_get_clearances_by_assignee
    )
    monkeypatch.setattr(acs.clearance_item, "search", mock_get_clearance_items)
    monkeypatch.setattr(acs.ccure_object, "search", mock_get_acs_doors)
    response = client.get(
        "/assignments/person2@email.com?get_doors=True", headers={"Authorization": "Bearer token"}
    )
    assert response.status_code == 200
    assert response.json() == {
        "assignments": [
            {
                "id": 5000,
                "name": "Hunt - Turnstiles",
                "can_revoke": True,
                "doors": {
                    "3000": "VRB-B-B103C-Test Door 1234",
                    "3001": "VRB-B-B103C-Test Door 5678",
                },
            },
            {"id": 5001, "name": "Library - Faculty Commons", "can_revoke": True, "doors": {}},
        ]
    }


def test_get_assignments_of_missing_person(db, fake_auth, monkeypatch):
    """
    It should fail gracefully when searching for assignments of someone who does not exist in ACS.
    """
    monkeypatch.setattr(acs.personnel, "search", lambda *_, **__: [])

    response = client.get(
        "/assignments/person2@email.com",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    assert response.json() == {"assignments": []}


def test_assign_clearances_as_admin(db, fake_auth, monkeypatch):
    """It should be able to assign clearances to an individual."""

    monkeypatch.setattr(ScheduledAction, "process", mock_process)
    monkeypatch.setattr(requests, "post", mock_request_post)

    raw_assignees = ["person2@email.com", "test3@email.com"]
    raw_clearance_ids = [5000, 5002, 5003, 5004]

    response = client.post(
        "/assignments/assign",
        headers={"Authorization": "Bearer token"},
        json={"assignee_emails": raw_assignees, "clearance_ids": raw_clearance_ids},
    )
    assert response.status_code == 200
    assert response.json() == {
        "succeeded": {
            "person2@email.com": {
                "5000": True,
                "5002": True,
                "5003": True,
                "5004": True,
            },
            "test3@email.com": {
                "5000": True,
                "5002": True,
                "5003": True,
                "5004": True,
            },
        },
        "failed": {},
        "pending": [],
    }


def test_revoke_clearances_as_admin(db, fake_auth, monkeypatch):
    """It should be able to revoke clearances from an individual."""

    monkeypatch.setattr(ScheduledAction, "process", mock_process)
    monkeypatch.setattr(requests, "post", mock_request_post)

    raw_assignees = ["person2@email.com", "GAtest3@email.com"]
    raw_clearance_ids = [
        5000,
        5002,
        5003,
        5004,
    ]

    response = client.post(
        "/assignments/revoke",
        headers={"Authorization": "Bearer token"},
        json={"assignee_emails": raw_assignees, "clearance_ids": raw_clearance_ids},
    )
    assert response.status_code == 200
    assert response.json() == {
        "succeeded": {
            "person2@email.com": {
                "5000": True,
                "5002": True,
                "5003": True,
                "5004": True,
            },
            "GAtest3@email.com": {
                "5000": True,
                "5002": True,
                "5003": True,
                "5004": True,
            },
        },
        "failed": {},
        "pending": [],
    }


def test_assign_too_many_clearances(db, fake_auth, monkeypatch, caplog):
    """
    It should fail assignment requests if it would give an individual too many clearances
    """
    monkeypatch.setattr(Personnel, "search_by_email", mock_find_by_email)
    monkeypatch.setattr(CcurePersonnel, "search", mock_acs_personnel_search)
    monkeypatch.setattr(CcureClearance, "search", mock_acs_clearance_search)
    monkeypatch.setattr(requests, "post", lambda *_, **__: FakeResponse())
    monkeypatch.setattr(acs.personnel, "search", lambda *_, **__: [])
    monkeypatch.setattr(
        acs.action.personnel,
        "get_assigned_clearances",
        mock_get_clearances_by_assignee_clearance_limit,
    )
    monkeypatch.setattr(acs.action.personnel, "assign_clearances", lambda *_, **__: None)

    raw_assignees = ["person2@email.com"]
    raw_clearance_ids = [5000, 5002, 5003, 5004]

    response = client.post(
        "/assignments/assign",
        headers={"Authorization": "Bearer token"},
        json={"assignee_emails": raw_assignees, "clearance_ids": raw_clearance_ids},
    )
    assert response.status_code == 200
    assert response.json() == {
        "succeeded": {},
        "failed": {
            "person2@email.com": {
                "5000": "This action would exceed this person's allowed number of clearances.",
                "5002": "This action would exceed this person's allowed number of clearances.",
                "5003": "This action would exceed this person's allowed number of clearances.",
                "5004": "This action would exceed this person's allowed number of clearances.",
            }
        },
        "already_completed": {},
        "pending": [],
    }


def test_assign_without_ccure_account(db, fake_auth, monkeypatch):
    """
    It should successfully assign the clearance, but the audit should show
    the logged-in user's name from the auth service
    """
    app.dependency_overrides[get_authorization] = override_get_authorization_admin
    monkeypatch.setattr(ScheduledAction, "process", mock_process)
    monkeypatch.setattr(requests, "post", mock_request_post)
    monkeypatch.setattr(Audit, "get_audit_log", mock_get_audit_log)

    assignment_response = client.post(
        "/assignments/assign",
        headers={"Authorization": "Bearer token"},
        json={
            "assignee_emails": ["person2@email.com"],
            "clearance_ids": [
                5000,
                5002,
            ],
        },
    )
    assert assignment_response.json() == {
        "succeeded": {"person2@email.com": {"5000": True, "5002": True}},
        "failed": {},
        "pending": [],
    }
    assert assignment_response.status_code == 200

    audit_response = client.get("/audit?limit=1", headers={"Authorization": "Bearer token"})
    assert audit_response.status_code == 200
    record = audit_response.json()["records"][0]
    assert record["assigner_name"] == "test assigner"


def test_get_assignments_as_liaison(db, fake_auth, monkeypatch):
    """
    It should be able to get all active assignments for an individual.
    """
    monkeypatch.setattr(acs.clearance, "get_property", mock_get_clearance_name)
    monkeypatch.setattr(
        ScheduledAction, "get_clearances_by_assignee", mock_get_clearances_by_assignee
    )
    monkeypatch.setattr(Clearance, "get_allowed", mock_get_allowed)
    app.dependency_overrides[get_authorization] = override_get_authorization_liaison

    response = client.get("/assignments/person2@email.com", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    assert response.json() == {"assignments": assigned_clearances}


def test_assign_clearances_as_liaison(db, fake_auth, monkeypatch):
    """
    It should assign clearances if the liaison has permission for all
    selected clearances. If any selected clearances are not in the
    liaison's permissions, all assignments should fail with a 403.
    """
    monkeypatch.setattr(ScheduledAction, "process", mock_process)
    monkeypatch.setattr(Clearance, "get_allowed", mock_get_allowed)
    monkeypatch.setattr(requests, "post", mock_request_post)

    app.dependency_overrides[get_authorization] = override_get_authorization_liaison

    raw_assignees = ["person2@email.com"]

    # assign more clearances than the liaison has permissions for
    raw_clearance_ids = [
        5000,  # Clearance1
        5002,  # Clearance2
        5003,
        5004,
    ]
    response = client.post(
        "/assignments/assign",
        headers={"Authorization": "Bearer token"},
        json={"assignee_emails": raw_assignees, "clearance_ids": raw_clearance_ids},
    )
    assert response.status_code == 403
    assert response.json().get("detail") == "Not authorized to assign all selected clearances"

    # assign only clearances the liaison has permissions for
    raw_clearance_ids = [
        5000,  # Clearance1
        5002,  # Clearance2
    ]
    response = client.post(
        "/assignments/assign",
        headers={"Authorization": "Bearer token"},
        json={"assignee_emails": raw_assignees, "clearance_ids": raw_clearance_ids},
    )
    assert response.status_code == 200
    assert response.json() == {
        "succeeded": {"person2@email.com": {"5000": True, "5002": True}},
        "failed": {},
        "pending": [],
    }


def test_revoke_clearances_as_liaison(db, fake_auth, monkeypatch):
    """
    It should revoke clearances if the liaison has permission for all
    selected clearances. If any selected clearances are not in the
    liaison's permissions, all revocations should fail with a 403.
    """

    monkeypatch.setattr(ScheduledAction, "process", mock_process)
    monkeypatch.setattr(Clearance, "get_allowed", mock_get_allowed)
    monkeypatch.setattr(requests, "post", mock_request_post)

    app.dependency_overrides[get_authorization] = override_get_authorization_liaison

    raw_assignees = ["person2@email.com"]

    # revoke more clearances than the liaison has permissions for
    raw_clearance_ids = [
        5000,  # Clearance1
        5002,  # Clearance2
        5003,
        5004,
    ]
    response = client.post(
        "/assignments/revoke",
        headers={"Authorization": "Bearer token"},
        json={"assignee_emails": raw_assignees, "clearance_ids": raw_clearance_ids},
    )
    assert response.status_code == 403
    assert response.json().get("detail") == "Not authorized to revoke all selected clearances"

    # revoke only clearances the liaison has permissions for
    raw_clearance_ids = [
        5000,  # Clearance1
        5002,  # Clearance2
    ]
    response = client.post(
        "/assignments/revoke",
        headers={"Authorization": "Bearer token"},
        json={"assignee_emails": raw_assignees, "clearance_ids": raw_clearance_ids},
    )
    assert response.status_code == 200
    assert response.json() == {
        "succeeded": {"person2@email.com": {"5000": True, "5002": True}},
        "failed": {},
        "pending": [],
    }


def test_assign_no_clearances(db, fake_auth, monkeypatch):
    """
    It should respond with an error if a request is made to assign an empty array of clearances.
    """

    def mock_assign(*_, **__):
        raise RuntimeError("At least one clearance ID is required.")

    monkeypatch.setattr(ScheduledAction, "process", mock_process)
    monkeypatch.setattr(Clearance, "get_allowed", mock_get_allowed)

    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    raw_assignees = ["person2@email.com"]

    response = client.post(
        "/assignments/assign",
        headers={"Authorization": "Bearer token"},
        json={"assignee_emails": raw_assignees, "clearance_ids": []},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "At least one clearance is required to assign a clearance."


def test_future_assign_clearances(db, fake_auth, monkeypatch):
    """It should create a future assign action"""
    monkeypatch.setattr(acs.personnel, "search", mock_acs_personnel_search)
    monkeypatch.setattr(acs.clearance, "search", mock_acs_clearance_search)
    monkeypatch.setattr(requests, "post", mock_request_post)

    raw_assignees = ["person2@email.com"]
    clearance_ids = [5000, 5002, 5003, 5004]

    assert db.scheduled_action.count_documents({}) == 0

    response = client.post(
        "/assignments/assign",
        headers={"Authorization": "Bearer token"},
        json={
            "assignee_emails": raw_assignees,
            "clearance_ids": clearance_ids,
            "start_time": "2034-06-21T04:00:00.000Z",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "succeeded": {},
        "failed": {},
        "already_completed": {},
        "pending": [
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5000,
                "action": "assign",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5002,
                "action": "assign",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5003,
                "action": "assign",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5004,
                "action": "assign",
                "action_time": "2034-06-21T04:00:00Z",
            },
        ],
    }

    assert db.scheduled_action.count_documents({}) == 4


def test_assign_temporary_clearances(db, fake_auth, monkeypatch):
    """It should assign the clearance and create a future revoke action"""
    monkeypatch.setattr(acs.personnel, "search", mock_acs_personnel_search)
    monkeypatch.setattr(acs.clearance, "search", mock_acs_clearance_search)
    monkeypatch.setattr(
        acs.action.personnel, "get_assigned_clearances", mock_get_assigned_clearances
    )
    monkeypatch.setattr(acs.action.personnel, "assign_clearances", mock_assign_clearances)
    monkeypatch.setattr(requests, "post", mock_request_post)

    raw_assignees = ["person2@email.com"]
    clearance_ids = [5000, 5002, 5003, 5004]

    assert db.scheduled_action.count_documents({}) == 0

    response = client.post(
        "/assignments/assign",
        headers={"Authorization": "Bearer token"},
        json={
            "assignee_emails": raw_assignees,
            "clearance_ids": clearance_ids,
            "end_time": "2034-06-21T04:00:00.000Z",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "succeeded": {
            "person2@email.com": {"5000": True, "5002": True, "5003": True, "5004": True}
        },
        "failed": {},
        "already_completed": {},
        "pending": [
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5000,
                "action": "revoke",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5002,
                "action": "revoke",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5003,
                "action": "revoke",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5004,
                "action": "revoke",
                "action_time": "2034-06-21T04:00:00Z",
            },
        ],
    }

    assert db.scheduled_action.count_documents({}) == 4


def test_assign_future_temporary_clearances(db, fake_auth, monkeypatch):
    """It should create future assign and revoke actions"""
    monkeypatch.setattr(acs.personnel, "search", mock_acs_personnel_search)
    monkeypatch.setattr(acs.clearance, "search", mock_acs_clearance_search)
    monkeypatch.setattr(
        acs.action.personnel, "get_assigned_clearances", mock_get_assigned_clearances
    )
    monkeypatch.setattr(requests, "post", mock_request_post)

    raw_assignees = ["person2@email.com"]
    clearance_ids = [5000, 5002, 5003, 5004]

    assert db.scheduled_action.count_documents({}) == 0

    response = client.post(
        "/assignments/assign",
        headers={"Authorization": "Bearer token"},
        json={
            "assignee_emails": raw_assignees,
            "clearance_ids": clearance_ids,
            "start_time": "2034-06-21T04:00:00.000Z",
            "end_time": "2054-06-21T04:00:00.000Z",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "succeeded": {},
        "failed": {},
        "already_completed": {},
        "pending": [
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5000,
                "action": "assign",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5002,
                "action": "assign",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5003,
                "action": "assign",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5004,
                "action": "assign",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5000,
                "action": "revoke",
                "action_time": "2054-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5002,
                "action": "revoke",
                "action_time": "2054-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5003,
                "action": "revoke",
                "action_time": "2054-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5004,
                "action": "revoke",
                "action_time": "2054-06-21T04:00:00Z",
            },
        ],
    }

    assert db.scheduled_action.count_documents({}) == 8


def test_future_revoke_clearances(db, fake_auth, monkeypatch):
    """It should create a future revoke action"""
    monkeypatch.setattr(acs.personnel, "search", mock_acs_personnel_search)
    monkeypatch.setattr(acs.clearance, "search", mock_acs_clearance_search)
    monkeypatch.setattr(
        acs.action.personnel, "get_assigned_clearances", mock_get_assigned_clearances
    )
    monkeypatch.setattr(requests, "post", mock_request_post)

    raw_assignees = ["person2@email.com", "person3@email.com"]
    clearance_ids = [5000, 5002, 5003, 5004]

    assert db.scheduled_action.count_documents({}) == 0

    response = client.post(
        "/assignments/revoke",
        headers={"Authorization": "Bearer token"},
        json={
            "assignee_emails": raw_assignees,
            "clearance_ids": clearance_ids,
            "action_time": "2034-06-21T04:00:00.000Z",
        },
    )
    assert response.status_code == 200
    assert response.json() == {
        "succeeded": {},
        "failed": {},
        "already_completed": {},
        "pending": [
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5000,
                "action": "revoke",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5002,
                "action": "revoke",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5003,
                "action": "revoke",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person2@email.com",
                "clearance_id": 5004,
                "action": "revoke",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person3@email.com",
                "clearance_id": 5000,
                "action": "revoke",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person3@email.com",
                "clearance_id": 5002,
                "action": "revoke",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person3@email.com",
                "clearance_id": 5003,
                "action": "revoke",
                "action_time": "2034-06-21T04:00:00Z",
            },
            {
                "assigner_email": "test_user@test.edu",
                "assignee_email": "person3@email.com",
                "clearance_id": 5004,
                "action": "revoke",
                "action_time": "2034-06-21T04:00:00Z",
            },
        ],
    }

    assert db.scheduled_action.count_documents({}) == 8


def test_bulk_schedule_actions(db, fake_auth, monkeypatch):
    """It should bulk schedule all actions in the scheduled_action collection."""
    monkeypatch.setattr(acs.personnel, "search", mock_acs_personnel_search)

    assert db.scheduled_action.count_documents({}) == 0

    now = datetime.now(timezone.utc)
    response = client.post(
        "/assignments/bulk-schedule-actions",
        headers={"Authorization": "Bearer token"},
        json=[
            {
                "assignee_email": "person2@email.com",
                "clearance_id": 10353,
                "action_type": "assign",
                "action_time": str(now + timedelta(days=5)),
            },
            {
                "assignee_email": "person2@email.com",
                "clearance_id": 10354,
                "action_type": "assign",
                "action_time": str(now - timedelta(days=5)),
            },
            {
                "assignee_email": "person2@email.com",
                "clearance_id": 5003,
                "action_type": "revoke",
                "action_time": str(now),
            },
        ],
    )

    assert len(response.json()) == 3
    assert db.scheduled_action.count_documents({}) == 3


def test_bulk_schedule_actions_case(db, fake_auth, monkeypatch):
    """bulk endpoint should convert all action types to lower case"""
    monkeypatch.setattr(acs.personnel, "search", mock_acs_personnel_search)
    monkeypatch.setattr(Personnel, "find_one", lambda email, _: Personnel({"EmailAddress": email}))
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_by_ids)

    now = datetime.now(timezone.utc)
    client.post(
        "/assignments/bulk-schedule-actions",
        headers={"Authorization": "Bearer token"},
        json=[
            {
                "assignee_email": "person2@email.com",
                "clearance_id": 10353,
                "action_type": "Assign",
                "action_time": str(now + timedelta(days=5)),
            },
            {
                "assignee_email": "person2@email.com",
                "clearance_id": 5003,
                "action_type": "Revoke",
                "action_time": str(now + timedelta(days=5)),
            },
        ],
    )

    assign_action = ScheduledAction.get(
        assignee_email="person2@email.com",
        clearance_id=10353,
    )
    assert assign_action["actions"][0]["action"] == "assign"

    revoke_action = ScheduledAction.get(
        assignee_email="person2@email.com",
        clearance_id=5003,
    )
    assert revoke_action["actions"][0]["action"] == "revoke"


def mock_personnel_search(email, *_):
    """Mock Personnel.search"""
    if email == "test_person1@test.edu":
        return [Personnel({"EmailAddress": "person1@email.com"})]
    return []


def mock_get_by_ids(ids):
    """Mock Clearance.get_by_ids"""
    return [{"id": _id, "name": f"clearance{i}"} for i, _id in enumerate(ids)]


def test_scheduled_actions_as_liaison(dbp, fake_auth, monkeypatch):
    """It should require an assigner email for liaisons."""
    monkeypatch.setattr(Personnel, "search", mock_personnel_search)
    monkeypatch.setattr(Personnel, "find_one", lambda email, _: None)
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_by_ids)
    monkeypatch.setattr(
        Clearance, "get_allowed", lambda *_, **__: [Clearance(6000, "C1"), Clearance(6001, "C2")]
    )

    app.dependency_overrides[get_authorization] = override_get_authorization_liaison

    # assigner email is not provided
    response = client.post(
        "/assignments/scheduled-actions",
        headers={"Authorization": "Bearer token"},
        json={"skip": 0, "limit": 50},
    )
    assert response.status_code == 400
    assert response.json() == {"detail": "An assigner_email is required"}

    # assigner email is provided
    response = client.post(
        "/assignments/scheduled-actions",
        headers={"Authorization": "Bearer token"},
        json={"skip": 0, "limit": 50, "assigner_email": "person1@email.com"},
    )
    assert response.status_code == 200
    assert len(response.json()["actions"]) == 8


def test_scheduled_actions_as_admin(dbp, fake_auth, monkeypatch):
    """It should not require an assigner email for admins."""
    monkeypatch.setattr(Personnel, "find_one", lambda email, _: Personnel({"EmailAddress": email}))
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_by_ids)

    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    response = client.post(
        "/assignments/scheduled-actions",
        headers={"Authorization": "Bearer token"},
        json={"skip": 0, "limit": 50},
    )
    assert response.status_code == 200
    assert len(response.json()["actions"]) == 8

    response = client.post(
        "/assignments/scheduled-actions",
        headers={"Authorization": "Bearer token"},
        json={"skip": 0, "limit": 50, "assigner_email": "person1@email.com"},
    )
    assert response.status_code == 200
    assert len(response.json()["actions"]) == 2


def test_scheduled_actions_total_count(dbp, fake_auth, monkeypatch):
    """A correct total count not influenced by the limit should be returned with the data"""
    monkeypatch.setattr(Personnel, "find_one", lambda email: Personnel({"EmailAddress": email}))
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_by_ids)

    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    response = client.post(
        "/assignments/scheduled-actions",
        headers={"Authorization": "Bearer token"},
        json={"skip": 0, "limit": 5},
    )
    assert response.status_code == 200
    assert response.json()["count"] == 8


def test_cancel_scheduled_action(dbp, fake_auth, monkeypatch):
    """The cancel_scheduled_actions route should set the right status on mongo objects"""
    monkeypatch.setattr(Personnel, "find_one", lambda email: Personnel({"EmailAddress": email}))
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_by_ids)

    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    action_id = "64625661a3f03b7bcddf2130"
    response = client.post(
        "/assignments/cancel-scheduled-actions",
        headers={"Authorization": "Bearer token"},
        json={"action_ids": [action_id]},
    )
    assert response.status_code == 200
    assert response.json()["cancellations"] == 1

    new_scheduled_action_results = client.post(
        "/assignments/scheduled-actions",
        headers={"Authorization": "Bearer token"},
        json={"skip": 0, "limit": 50},
    )
    actions = new_scheduled_action_results.json()["actions"]
    cancelled_actions = [action for action in actions if action["status"] == "cancelled"]
    assert len(cancelled_actions) == 1
    assert cancelled_actions[0]["_id"] == action_id
