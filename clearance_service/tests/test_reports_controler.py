"""Tests for /reports endpoints"""
from datetime import datetime, timezone

from acslib.ccure.base import CcureACS
from fastapi.testclient import TestClient
from main import app

from clearance_service.crud.reports import UsageReport
from clearance_service.models import acs
from clearance_service.models.clearance import Clearance
from clearance_service.tests.override_get_authorization import override_get_authorization_admin
from clearance_service.util.authorization import get_authorization

app.dependency_overrides[get_authorization] = override_get_authorization_admin
test_client = TestClient(app)

now = datetime.now(timezone.utc)


def mock_get_clearance_assignees(*_, **kwargs):
    """mock acslib.actions.personnel.get_assigned_clearances"""
    return [
        {
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.PersonnelClearancePair",
            "ClearanceID": 4001,
            "ObjectID": 6931,
            "PersonnelID": 3000,
            # etc
        },
        {
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.PersonnelClearancePair",
            "ClearanceID": 4001,
            "ObjectID": 6931,
            "PersonnelID": 3001,
        },
    ][: kwargs.get("page_size", 3)]


def mock_get_clearance_items(*_, **kwargs):
    """mock acslib.clearance_item.search"""
    items = [
        {
            "Name": "DoorItemA",
            "ObjectID": 5000,
            "ClearanceID": 10356,
            "DoorID": 5000,
            "ElevatorID": None,
            "ScheduleID": 2,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.ClearanceItem",
            # etc
        },
        {
            "Name": "DoorItemB",
            "ObjectID": 5001,
            "ClearanceID": 10356,
            "DoorID": 5001,
            "ElevatorID": None,
            "ScheduleID": 2,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.ClearanceItem",
        },
        {
            "Name": "ElevatorItemA",
            "ObjectID": 5004,
            "ClearanceID": 10356,
            "DoorID": None,
            "ElevatorID": 5000,
            "ScheduleID": 2,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.ClearanceItem",
        },
        {
            "Name": "DoorItemC",
            "ObjectID": 5002,
            "ClearanceID": 10357,
            "DoorID": 5004,
            "ScheduleID": 2,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.ClearanceItem",
        },
        {
            "Name": "DoorItemD",
            "ObjectID": 5003,
            "ClearanceID": 10357,
            "DoorID": None,
            "ElevatorID": 5000,
            "ScheduleID": 2,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.ClearanceItem",
        },
    ][: kwargs.get("page_size", 1000)]
    if item_ids := kwargs.get("terms"):
        val = [item for item in items if item["ClearanceID"] == item_ids[0]]
        return val
    return items


def mock_get_schedules_by_object_id(*_, **kwargs):
    """mock acslib search for TimeSpec objects"""
    return [{"ObjectID": 2, "Name": "Always"}]


def mock_get_people_by_object_id(*_, **kwargs):
    """mock acslib.personnel.search"""
    return [
        {
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.Personnel",
            "Disabled": False,
            "FirstName": "Lisa",
            "LastName": "Mena",
            "MiddleName": "",
            "Name": "Mena, Lisa",
            "ObjectID": 3000,
            "ProperName": "Lisa Mena",
            "EmailAddress": "lmena@university.edu",
            # etc
        },
        {
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.Personnel",
            "Disabled": False,
            "FirstName": "Shawn",
            "LastName": "Kemp",
            "MiddleName": "",
            "Name": "Mena, Lisa",
            "ObjectID": 3001,
            "ProperName": "Lisa Mena",
            "EmailAddress": "lmena@university.edu",
        },
    ][: 1 if "mena" in kwargs["where_clause"].lower() else 2]


def mock_search_clearance_items(doors_only: bool = True, *_, **__):
    """Mock acslib.clearance_item.search"""
    doors = [
        {
            "*state": 1,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
            "GUID": "6b452ea8-ddbd-47d1-8908-76817aaa11f4",
            "Name": "VRB-B-B103B-Test Door 1",
            "ControllerClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarController",
            "MaintenanceMode": False,
            "RequireManualActionInstructions": False,
            "ModeStatus": 2,
            "OpenStatus": None,
            "AlarmStateStatus": 1,
            "ObjectID": 5000,
            "*appServer": "VRB-C9K-02",
            "*PK": ["ObjectID"],
        },
        {
            "*state": 1,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
            "GUID": "95ea96cd-612a-45e3-8d54-f0ffb7a43f8a",
            "Name": "VRB-B-B103C-Test Door 2",
            "ControllerClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarController",
            "MaintenanceMode": False,
            "RequireManualActionInstructions": False,
            "ModeStatus": 2,
            "OpenStatus": None,
            "AlarmStateStatus": 1,
            "ObjectID": 5001,
            "*appServer": "VRB-C9K-02",
            "*PK": ["ObjectID"],
        },
        {
            "*state": 1,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
            "GUID": "3b1f4cd8-9b37-4f44-be5f-e7fb337b4001",
            "Name": "VRB-B-B103D-Test Door 3",
            "ControllerClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarController",
            "MaintenanceMode": False,
            "RequireManualActionInstructions": False,
            "ModeStatus": 2,
            "OpenStatus": None,
            "AlarmStateStatus": 1,
            "ObjectID": 5002,
            "*appServer": "VRB-C9K-02",
            "*PK": ["ObjectID"],
        },
        {
            "*state": 1,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
            "GUID": "4aaff490-d041-44ed-ba17-01c6498781a2",
            "Name": "VRB-B-B103D-Test Door 4",
            "ControllerClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarController",
            "MaintenanceMode": False,
            "RequireManualActionInstructions": False,
            "ModeStatus": 2,
            "OpenStatus": None,
            "AlarmStateStatus": 1,
            "ObjectID": 5003,
            "*appServer": "VRB-C9K-02",
            "*PK": ["ObjectID"],
        },
    ]
    if doors_only:
        return doors
    # include an elevator:
    return doors + [
        {
            "*state": 1,
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.Elevator",
            "GUID": "b541a4f9-d9bd-41fa-bc3f-881f911dc473",
            "Name": "VRB-B-B103C-Elevator 1",
            "ControllerClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarController",
            "MaintenanceMode": False,
            "ObjectID": 5000,
            "*appServer": "VRB-C9K-02",
            "*PK": ["ObjectID"],
        }
    ]


def test_monthly_by_user(dbp, fake_auth, time_machine):
    """
    Test the /reports/usage/monthly-by-user endpoint
    It should:
        - have a row for each person for each month
        - include the correct totals for each person for each month
        - not include assignments from outside the last 12 months
    """
    time_machine.move_to(datetime(now.year, 8, 15, tzinfo=timezone.utc))
    response = test_client.get(
        "/reports/usage/monthly-by-user",
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200

    content = response._content.strip()
    assert isinstance(content, bytes)

    # 12 months x 2 people + a header row
    lines = [str(line.strip()).lstrip("b'").rstrip("'") for line in content.split(b"\n")]
    assert len(lines) == 25

    person1_assignments = [
        int(record.split(",")[4]) for record in lines if record.split(",")[0] == "person1"
    ]
    assert person1_assignments == [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 1, 2]

    person2_assignments = [
        int(record.split(",")[4]) for record in lines if record.split(",")[0] == "person2"
    ]
    assert person2_assignments == [0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 2]


def test_run_in_december(dbp, fake_auth, time_machine):
    """
    It should set the date range correctly. When the endpoint is called in December,
    the results should include the previous December through November of the current year.
    """
    time_machine.move_to(
        datetime(now.year, month=12, day=15, hour=10, minute=35, tzinfo=timezone.utc)
    )
    UsageReport.date_range = None
    response = test_client.get(
        "/reports/usage/monthly-by-user",
        headers={"Authorization": "Bearer token"},
    )
    content = response._content.strip()
    lines = [str(line.strip()).lstrip("b'").rstrip("'") for line in content.split(b"\n")]

    # verify that user rows go from last december through this november
    person1_rows = [row for row in lines if "person1" in row]
    assert str(now.year - 1) in person1_rows[0]
    assert "December" in person1_rows[0]
    assert str(now.year) in person1_rows[-1]
    assert "November" in person1_rows[-1]


def test_run_in_january(dbp, fake_auth, time_machine):
    """
    It should set the date range correctly. When the endpoint is called in January,
    the results should include January through December of the previous year.
    """
    time_machine.move_to(
        datetime(now.year, month=1, day=15, hour=10, minute=35, tzinfo=timezone.utc)
    )
    UsageReport.date_range = None
    response = test_client.get(
        "/reports/usage/monthly-by-user",
        headers={"Authorization": "Bearer token"},
    )
    content = response._content.strip()
    lines = [str(line.strip()).lstrip("b'").rstrip("'") for line in content.split(b"\n")]

    # verify that user rows go from last january through last december
    person1_rows = [row for row in lines if "person1" in row]
    assert str(now.year - 1) in person1_rows[0]
    assert "January" in person1_rows[0]
    assert str(now.year - 1) in person1_rows[-1]
    assert "December" in person1_rows[-1]


def test_clearance_assignee_report(fake_auth, monkeypatch):
    """It should give a report of the liaison's clearances, limiting assignees per clearance to 3"""
    monkeypatch.setattr(CcureACS, "search", mock_get_clearance_assignees)
    monkeypatch.setattr(acs.personnel, "search", mock_get_people_by_object_id)
    monkeypatch.setattr(
        Clearance,
        "get_allowed",
        lambda *_, **__: [
            Clearance(_id=4001, name="Clearance1"),
            Clearance(_id=4002, name="Clearance2"),
        ],
    )
    response = test_client.get(
        "/reports/clearances/persons",
        headers={"Authorization": "Bearer token"},
    )

    json = response.json()
    assert isinstance(json, dict)
    assert len(json) == 2
    assert "total_clearances" in json
    assert json["total_clearances"] == 2
    assert "clearances" in json
    clearances = json["clearances"]
    assert "Clearance1" in json["clearances"]
    clearance1 = clearances["Clearance1"]
    assert len(clearance1) == 3
    assert len(clearance1["assignees"]) == 2
    assert clearance1["clearance_id"] == 4001
    assert clearance1["assignee_count"] == 2
    assignee = clearance1["assignees"][0]
    assert isinstance(assignee, dict)
    assert len(assignee) == 2
    assert "Clearance2" in clearances
    clearance2 = clearances["Clearance2"]
    assert len(clearance2["assignees"]) == 0
    assert clearance2["assignee_count"] == 0


def test_clearance_assignee_report_page_2(fake_auth, monkeypatch):
    """It should return the second page of reports."""
    monkeypatch.setattr(CcureACS, "search", mock_get_clearance_assignees)
    monkeypatch.setattr(acs.personnel, "search", mock_get_people_by_object_id)
    monkeypatch.setattr(
        Clearance,
        "get_allowed",
        lambda *_, **__: [
            Clearance(_id=4000, name="Clearance1"),
            Clearance(_id=4001, name="Clearance2"),
        ],
    )
    response = test_client.get(
        "/reports/clearances/persons?clearances_limit=1&clearances_skip=1",
        headers={"Authorization": "Bearer token"},
    )

    json = response.json()
    print(json)
    assert isinstance(json, dict)
    assert len(json) == 2
    assert "total_clearances" in json
    assert json["total_clearances"] == 2
    assert "clearances" in json
    clearances = json["clearances"]
    assert "Clearance1" not in json["clearances"]
    assert "Clearance2" in clearances


def test_assignee_report_unauthorized_clearance(fake_auth, monkeypatch):
    """It should not allow a liaison to generate a report for a clearance they can't assign"""
    monkeypatch.setattr(CcureACS, "search", mock_get_clearance_assignees)
    monkeypatch.setattr(acs.personnel, "search", mock_get_people_by_object_id)
    monkeypatch.setattr(
        Clearance,
        "get_allowed",
        lambda *_, **__: [
            Clearance(_id=4000, name="Clearance1"),
            Clearance(_id=4001, name="Clearance2"),
        ],
    )
    response = test_client.get(
        "/reports/clearances/persons?clearance_id=4444",
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 403


def test_assignee_report_invalid_page(fake_auth, monkeypatch):
    """It should only find more assignees for a single clearance"""
    monkeypatch.setattr(CcureACS, "search", mock_get_clearance_assignees)
    monkeypatch.setattr(acs.personnel, "search", mock_get_people_by_object_id)
    monkeypatch.setattr(
        Clearance,
        "get_allowed",
        lambda *_, **__: [
            Clearance(_id=4000, name="Clearance1"),
            Clearance(_id=4001, name="Clearance2"),
        ],
    )
    response = test_client.get(
        "/reports/clearances/persons?assignees_page=2",
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 400


def test_assignee_report_specify_clearance(fake_auth, monkeypatch):
    """It should be able to find assignees for a single clearance"""
    monkeypatch.setattr(CcureACS, "search", mock_get_clearance_assignees)
    monkeypatch.setattr(acs.personnel, "search", mock_get_people_by_object_id)
    monkeypatch.setattr(
        Clearance,
        "get_allowed",
        lambda *_, **__: [
            Clearance(_id=4001, name="Clearance1"),
            Clearance(_id=4002, name="Clearance2"),
        ],
    )
    response = test_client.get(
        "/reports/clearances/persons?clearance_id=4001",
        headers={"Authorization": "Bearer token"},
    )
    clearances = response.json()["clearances"]
    assert len(clearances) == 1
    assert "Clearance1" in clearances
    assert len(clearances["Clearance1"]["assignees"]) == 2


def test_assignee_report_limit_assignees(fake_auth, monkeypatch):
    """It should be able to filter assignees"""
    monkeypatch.setattr(CcureACS, "search", mock_get_clearance_assignees)
    monkeypatch.setattr(acs.personnel, "search", mock_get_people_by_object_id)
    monkeypatch.setattr(acs.action.clearance, "get_assignees", mock_get_clearance_assignees)
    monkeypatch.setattr(
        Clearance,
        "get_allowed",
        lambda *_, **__: [
            Clearance(_id=4000, name="Clearance1"),
            Clearance(_id=4001, name="Clearance2"),
        ],
    )
    response = test_client.get(
        "/reports/clearances/persons?assignee_name=Lisa+Mena",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200

    data = response.json()
    response_assignees = []
    for _, clearance in data["clearances"].items():
        if clearance["assignees"]:
            for assignee in clearance["assignees"]:
                response_assignees.append(f"{assignee['first']} {assignee['last']}")
    assert response_assignees == ["Lisa Mena"]


def test_assignee_report_no_allowed_clearances(fake_auth, monkeypatch):
    """It should handle case where liaison has no allowed clearances"""
    monkeypatch.setattr(CcureACS, "search", mock_get_clearance_assignees)
    monkeypatch.setattr(acs.personnel, "search", mock_get_people_by_object_id)
    monkeypatch.setattr(acs.action.clearance, "get_assignees", mock_get_clearance_assignees)
    monkeypatch.setattr(
        Clearance,
        "get_allowed",
        lambda *_, **__: [],
    )

    response = test_client.get(
        "/reports/clearances/persons",
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    data = response.json()
    assert data["total_clearances"] == 0
    assert data["clearances"] == {}


def test_clearance_door_report(fake_auth, monkeypatch):
    """
    It should give a report of the doors tied to a liaison's clearances,
    limiting doors per clearance to 3.
    """
    monkeypatch.setattr(CcureACS, "search", mock_get_clearance_assignees)
    monkeypatch.setattr(acs.clearance_item, "search", mock_get_clearance_items)
    monkeypatch.setattr(acs.ccure_object, "search", mock_get_schedules_by_object_id)
    monkeypatch.setattr(
        Clearance,
        "get_allowed",
        lambda *_, **__: [Clearance(_id=10356, name="Clearance1")],
    )
    response = test_client.get(
        "/reports/clearances/doors",
        headers={"Authorization": "Bearer token"},
    )

    json = response.json()
    assert isinstance(json, dict)
    assert len(json) == 2
    assert "total_clearances" in json
    assert json["total_clearances"] == 1


def test_door_report_door_filter(fake_auth, monkeypatch):
    """
    It should give a report with clearances that have a particular door.
    """
    monkeypatch.setattr(acs.clearance_item, "search", mock_get_clearance_items)
    monkeypatch.setattr(acs.ccure_object, "search", mock_get_schedules_by_object_id)
    monkeypatch.setattr(
        Clearance,
        "get_allowed",
        lambda *_, **__: [
            Clearance(_id=10356, name="Clearance1"),
            Clearance(_id=10357, name="Clearance2"),
        ],
    )
    response = test_client.get(
        "/reports/clearances/doors?door_ids=5000",
        headers={"Authorization": "Bearer token"},
    )

    json = response.json()

    assert isinstance(json, dict)
    assert len(json) == 2
    assert "total_clearances" in json
    assert json["total_clearances"] == 1
    assert "clearances" in json
    clearances = json["clearances"]
    assert "Clearance1" in json["clearances"]
    clearance1 = clearances["Clearance1"]
    assert len(clearance1) == 3
    assert len(clearance1["doors"]) == 3
    assert clearance1["clearance_id"] == 10356
    assert clearance1["door_count"] == 3
    door = clearance1["doors"][0]
    assert isinstance(door, dict)
    assert len(door) == 6


def test_door_report_no_assigned_clearances(fake_auth, monkeypatch):
    """
    It should give an empty report if the user has no assignable clearances
    """
    monkeypatch.setattr(acs.clearance_item, "search", mock_get_clearance_items)
    monkeypatch.setattr(acs.ccure_object, "search", mock_get_schedules_by_object_id)
    monkeypatch.setattr(
        Clearance,
        "get_allowed",
        lambda *_, **__: [],
    )
    response = test_client.get(
        "/reports/clearances/doors?door_ids=5000",
        headers={"Authorization": "Bearer token"},
    )
    json = response.json()

    assert isinstance(json, dict)
    assert json == {"total_clearances": 0, "clearances": {}}


def test_door_report_unauthorized_clearance(fake_auth, monkeypatch):
    """It should not allow a liaison to generate a report for a clearance they can't assign"""
    monkeypatch.setattr(
        Clearance,
        "get_allowed",
        lambda *_, **__: [
            Clearance(_id=10356, name="Clearance1"),
            Clearance(_id=10357, name="Clearance2"),
        ],
    )
    response = test_client.get(
        "/reports/clearances/doors?clearance_id=4444",
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 403


def test_door_report_specify_clearance(fake_auth, monkeypatch):
    """It should be able to find doors for a single clearance"""
    monkeypatch.setattr(acs.clearance_item, "search", mock_get_clearance_items)
    monkeypatch.setattr(acs.ccure_object, "search", mock_get_schedules_by_object_id)
    monkeypatch.setattr(
        Clearance,
        "get_allowed",
        lambda *_, **__: [Clearance(_id=10356, name="Clearance1")],
    )
    response = test_client.get(
        "/reports/clearances/doors?clearance_id=10356",
        headers={"Authorization": "Bearer token"},
    )
    clearances = response.json()["clearances"]
    assert len(clearances) == 1
    assert "Clearance1" in clearances
    assert len(clearances["Clearance1"]["doors"]) == 3


def test_search_items(fake_auth, monkeypatch):
    """It should search for clearance items and return correctly-formatted dicts"""
    monkeypatch.setattr(acs.ccure_object, "search", mock_search_clearance_items)
    response = test_client.get(
        "/reports/search-items",
        headers={"Authorization": "Bearer token"},
    ).json()
    assert len(response) == 4
    assert all(len(item) == 3 for item in response)
