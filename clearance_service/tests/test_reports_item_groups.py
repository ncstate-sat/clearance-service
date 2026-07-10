"""Tests for /reports endpoints"""
from datetime import datetime, timezone
from unittest.mock import Mock

from fastapi.testclient import TestClient
from main import app

from clearance_service.models import acs
from clearance_service.models.clearance import Clearance
from clearance_service.tests.override_get_authorization import override_get_authorization_admin
from clearance_service.util.authorization import get_authorization

app.dependency_overrides[get_authorization] = override_get_authorization_admin
test_client = TestClient(app)

now = datetime.now(timezone.utc)


def get_mock_clearance_item(
    name,
    object_id,
    clearance_id,
    door_id=None,
    elevator_id=None,
    door_group_id=None,
    elevator_group_id=None,
):
    return {
        "Name": "DoorGroup1",
        "ObjectID": object_id,
        "ClearanceID": clearance_id,
        "DoorID": door_id,
        "ElevatorID": elevator_id,
        "DoorGroupID": door_group_id,
        "ElevatorGroupID": elevator_group_id,
    }


def get_mock_group_members(target_object_id, group_id, object_id):
    return {
        "*state": 1,
        "ClassType": "SoftwareHouse.CrossFire.Common.Objects.GroupMember",
        "GUID": "7e47b2e6-2d09-46ed-a8c3-0a18507842fc",
        "TargetObjectID": target_object_id,
        "GroupID": group_id,
        "ObjectID": object_id,
        "*PK": ["ObjectID"],
        "*appServer": "CCURE.PHYSEC.NCSU.EDU",
    }


def get_mock_door(object_id):
    return {
        "*state": 1,
        "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
        "GUID": "95ea96cd-612a-45e3-8d54-f0ffb7a43f8a",
        "Name": f"VRB-B-B103C-Test Door {object_id}",
        "ControllerClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarController",
        "MaintenanceMode": False,
        "RequireManualActionInstructions": False,
        "ModeStatus": 2,
        "OpenStatus": None,
        "AlarmStateStatus": 1,
        "ObjectID": object_id,
        "*appServer": "VRB-C9K-02",
        "*PK": ["ObjectID"],
    }


def get_mock_elevator(object_id):
    return {
        "*state": 1,
        "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.Elevator",
        "GUID": "95ea96cd-612a-45e3-8d54-f0ffb7a43f8a",
        "Name": f"VRB-B-B103C-Test Elevator {object_id}",
        "ControllerClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.ElevatorController",
        "MaintenanceMode": False,
        "RequireManualActionInstructions": False,
        "ModeStatus": 2,
        "OpenStatus": None,
        "AlarmStateStatus": 1,
        "ObjectID": object_id,
        "*appServer": "VRB-C9K-02",
        "*PK": ["ObjectID"],
    }


MOCK_SCHEDULES = [{"ObjectID": 2, "Name": "Always"}]

EXPECTED_DOORS = [
    {
        "door_id": 5300,
        "elevator_id": None,
        "id": None,
        "is_elevator": False,
        "name": "VRB-B-B103C-Test Door 2",
        "schedule_name": None,
    },
    {
        "door_id": 5301,
        "elevator_id": None,
        "id": None,
        "is_elevator": False,
        "name": "VRB-B-B103C-Test Door 2",
        "schedule_name": None,
    },
    {
        "door_id": 5302,
        "elevator_id": None,
        "id": None,
        "is_elevator": False,
        "name": "VRB-B-B103C-Test Door 2",
        "schedule_name": None,
    },
]


def test_door_report_door_group(fake_auth, monkeypatch):
    """It should return doors in a door group related to a clearance"""
    test_door_ids = [5300, 5301, 5302]
    test_group_id = 1
    test_clearance_id = 1234
    expected_response_doors = [
        {
            "door_id": door_id,
            "elevator_id": None,
            "id": None,
            "is_elevator": False,
            "name": f"VRB-B-B103C-Test Door {door_id}",
            "schedule_name": None,
        }
        for door_id in test_door_ids
    ]

    mock_clearance_items = [
        get_mock_clearance_item(
            name="TestDoorGroup1",
            object_id=5000,
            clearance_id=test_clearance_id,
            door_group_id=test_group_id,
        )
    ]
    mock_doors_from_door_group = [get_mock_door(object_id) for object_id in test_door_ids]
    mock_group_members = [
        get_mock_group_members(target_object_id, test_group_id, target_object_id)
        for target_object_id in test_door_ids
    ]

    clearance_items_mock = Mock(side_effect=[mock_clearance_items, mock_doors_from_door_group, []])
    group_members_mock = Mock(side_effect=[mock_group_members])

    def ccure_obj_search_mock(object_type: str, *_, **__):
        if "elevator" in object_type.lower():
            return []
        if "door" in object_type.lower():
            return mock_doors_from_door_group
        if "timespec" in object_type.lower():
            return MOCK_SCHEDULES

    monkeypatch.setattr(acs.clearance_item, "search", clearance_items_mock)
    monkeypatch.setattr(acs.group_member, "search", group_members_mock)
    monkeypatch.setattr(acs.ccure_object, "search", ccure_obj_search_mock)
    monkeypatch.setattr(
        Clearance,
        "get_allowed",
        lambda *_, **__: [Clearance(_id=1234, name="ClearanceWithDoorGroup")],
    )

    response = test_client.get(
        "/reports/clearances/doors?clearance_id=1234",
        headers={"Authorization": "Bearer token"},
    )
    response_data = response.json()
    assert response_data["total_clearances"] == 1
    assert response_data["clearances"]["ClearanceWithDoorGroup"]["clearance_id"] == 1234
    assert response_data["clearances"]["ClearanceWithDoorGroup"]["door_count"] == 3
    assert response_data["clearances"]["ClearanceWithDoorGroup"]["doors"] == expected_response_doors


def test_door_report_elevator_group(fake_auth, monkeypatch):
    """It should return elevators in an elevator group related to a clearance"""
    test_elevator_ids = [5400, 5401, 5402]
    test_group_id = 2
    test_clearance_id = 1234
    expected_response_doors = [
        {
            "door_id": None,
            "elevator_id": elevator_id,
            "id": None,
            "is_elevator": True,
            "name": f"VRB-B-B103C-Test Elevator {elevator_id}",
            "schedule_name": None,
        }
        for elevator_id in test_elevator_ids
    ]

    mock_clearance_items = [
        get_mock_clearance_item(
            name="TestElevatorGroup1",
            object_id=5000,
            clearance_id=test_clearance_id,
            elevator_group_id=test_group_id,
        )
    ]
    mock_elevators_from_elevator_group = [
        get_mock_elevator(object_id) for object_id in test_elevator_ids
    ]
    mock_group_members = [
        get_mock_group_members(target_object_id, test_group_id, target_object_id)
        for target_object_id in test_elevator_ids
    ]

    # The order here in the clearance_items mock is actually extremely important for the
    # test to work correctly
    # Since everything goes through the single search method call, the order of this list determines
    # whether the returned items are door items or elevator items,
    # since the code searches for doors first and then elevators.
    clearance_items_mock = Mock(
        side_effect=[mock_clearance_items, [], mock_elevators_from_elevator_group]
    )
    group_members_mock = Mock(side_effect=[mock_group_members])

    def ccure_obj_search_mock(object_type: str, *_, **__):
        if "elevator" in object_type.lower():
            return mock_elevators_from_elevator_group
        if "door" in object_type.lower():
            return []
        if "timespec" in object_type.lower():
            return MOCK_SCHEDULES

    monkeypatch.setattr(acs.clearance_item, "search", clearance_items_mock)
    monkeypatch.setattr(acs.group_member, "search", group_members_mock)
    monkeypatch.setattr(acs.ccure_object, "search", ccure_obj_search_mock)
    monkeypatch.setattr(
        Clearance,
        "get_allowed",
        lambda *_, **__: [Clearance(_id=1234, name="ClearanceWithDoorGroup")],
    )

    response = test_client.get(
        "/reports/clearances/doors?clearance_id=1234",
        headers={"Authorization": "Bearer token"},
    )
    response_data = response.json()
    assert response_data["total_clearances"] == 1
    assert (
        response_data["clearances"]["ClearanceWithDoorGroup"]["clearance_id"] == test_clearance_id
    )
    assert response_data["clearances"]["ClearanceWithDoorGroup"]["door_count"] == 3
    assert response_data["clearances"]["ClearanceWithDoorGroup"]["doors"] == expected_response_doors


def test_door_report_elevators_and_doors(fake_auth, monkeypatch):
    """It should return elevators in an elevator group related to a clearance"""
    test_elevator_ids = [5400, 5401, 5402]
    test_group_id = 2
    test_clearance_id = 1234
    expected_response_doors = [
        {
            "door_id": None,
            "elevator_id": elevator_id,
            "id": None,
            "is_elevator": True,
            "name": f"VRB-B-B103C-Test Elevator {elevator_id}",
            "schedule_name": None,
        }
        for elevator_id in test_elevator_ids
    ]

    mock_clearance_items = [
        get_mock_clearance_item(
            name="TestElevatorGroup1",
            object_id=5000,
            clearance_id=test_clearance_id,
            elevator_group_id=test_group_id,
        )
    ]
    mock_elevators_from_elevator_group = [
        get_mock_elevator(object_id) for object_id in test_elevator_ids
    ]
    mock_group_members = [
        get_mock_group_members(target_object_id, test_group_id, target_object_id)
        for target_object_id in test_elevator_ids
    ]

    # The order here in the clearance_items mock is actually extremely important for
    # the test to work correctly
    # Since everything goes through the single search method call, the order of this list determines
    # whether the returned items are door items or elevator items,
    # since the code searches for doors first and then elevators.
    clearance_items_mock = Mock(
        side_effect=[mock_clearance_items, [], mock_elevators_from_elevator_group]
    )
    group_members_mock = Mock(side_effect=[mock_group_members])

    def ccure_obj_search_mock(object_type: str, *_, **__):
        if "elevator" in object_type.lower():
            return mock_elevators_from_elevator_group
        if "door" in object_type.lower():
            return []
        if "timespec" in object_type.lower():
            return MOCK_SCHEDULES

    monkeypatch.setattr(acs.clearance_item, "search", clearance_items_mock)
    monkeypatch.setattr(acs.group_member, "search", group_members_mock)
    monkeypatch.setattr(acs.ccure_object, "search", ccure_obj_search_mock)
    monkeypatch.setattr(
        Clearance,
        "get_allowed",
        lambda *_, **__: [Clearance(_id=1234, name="ClearanceWithDoorGroup")],
    )

    response = test_client.get(
        "/reports/clearances/doors?clearance_id=1234",
        headers={"Authorization": "Bearer token"},
    )
    response_data = response.json()
    assert response_data["total_clearances"] == 1
    assert (
        response_data["clearances"]["ClearanceWithDoorGroup"]["clearance_id"] == test_clearance_id
    )
    assert response_data["clearances"]["ClearanceWithDoorGroup"]["door_count"] == 3
    assert response_data["clearances"]["ClearanceWithDoorGroup"]["doors"] == expected_response_doors
