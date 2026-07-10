"""Tests for the space_schedules endpoints"""

from datetime import datetime

from bson import ObjectId
from fastapi.testclient import TestClient
from main import app

from clearance_service.tests.override_get_authorization import (
    override_get_authorization_admin,
    override_get_authorization_liaison,
)
from clearance_service.util.authorization import get_authorization

client = TestClient(app)
now = datetime.now()


def test_create_space_schedule(db, fake_auth):
    """It should correctly handle create requests"""
    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    response = client.post(
        "/space-schedules/create",
        json={
            "space_id": "68a36894e6decd139abbe087",
            "action_time": "2026-09-27T21:15:00.000Z",
            "action_type": "lock",
            "series_name": "test_seriesC",
        },
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 201
    json = response.json()
    assert isinstance(json, dict)
    assert "message" in json
    assert json["message"] == "Created schedule to lock space"


def test_search_spaces_as_admin(dbp, fake_auth):
    """It should handle a search request"""
    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    # get all schedules
    response = client.get(
        "/space-schedules/search",
        params={},
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200
    json = response.json()
    assert isinstance(json, list)
    assert len(json) == 3
    space = json[0]
    assert isinstance(space, dict)
    assert len(space) == 8

    # search by series name
    response = client.get(
        "/space-schedules/search",
        params={"series_name": "test_series1"},
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200
    json = response.json()
    assert isinstance(json, list)
    assert len(json) == 2


def test_search_spaces_as_liaison(dbp, fake_auth):
    """It should limit search results to schedules created by the user"""
    app.dependency_overrides[get_authorization] = override_get_authorization_liaison

    # get all schedules
    response = client.get(
        "/space-schedules/search",
        params={},
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200
    json = response.json()
    assert isinstance(json, list)
    assert len(json) == 2

    # search by series name
    response = client.get(
        "/space-schedules/search",
        params={"series_name": "test_series1"},
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200
    json = response.json()
    assert isinstance(json, list)
    assert len(json) == 1


def test_update_space_schedule_as_admin(dbp, fake_auth):
    """It should successfully update a space schedule"""
    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    schedule_before_update = dbp.space_schedule.find_one(
        {"_id": ObjectId("68d45dd062efa1978c6b8549")}
    )

    update_response = client.put(
        "/space-schedules/update",
        json={
            "schedule_id": "68d45dd062efa1978c6b8549",
            "space_id": "68a36894e6decd139abbe089",
            # action time is unchanged
        },
        headers={"Authorization": "Bearer token"},
    )

    assert update_response.status_code == 200
    json = update_response.json()
    assert isinstance(json, dict)
    assert "message" in json
    assert json["message"] == "Updated space schedule"

    schedule_after_update = dbp.space_schedule.find_one(
        {"_id": ObjectId("68d45dd062efa1978c6b8549")}
    )
    assert schedule_before_update["_id"] == schedule_after_update["_id"]
    assert schedule_before_update["action_time"] == schedule_after_update["action_time"]
    assert schedule_after_update["space_id"] == ObjectId("68a36894e6decd139abbe089")

    update_response = client.put(
        "/space-schedules/update",
        json={
            "schedule_id": "68d45dd062efa1978c6b8549",
            "action_time": "2005-09-27T21:15:00.000Z",
            # space ID is unchanged
        },
        headers={"Authorization": "Bearer token"},
    )

    assert update_response.status_code == 200
    assert json["message"] == "Updated space schedule"

    schedule_after_update = dbp.space_schedule.find_one(
        {"_id": ObjectId("68d45dd062efa1978c6b8549")}
    )
    assert schedule_after_update["space_id"] == ObjectId("68a36894e6decd139abbe089")
    assert isinstance(schedule_after_update["action_time"], datetime)
    assert schedule_after_update["action_time"].year == 2005


def test_update_space_schedule_as_liaison(dbp, fake_auth):
    """It should successfully update a space schedule that was created by the user"""
    app.dependency_overrides[get_authorization] = override_get_authorization_liaison

    schedule_before_update = dbp.space_schedule.find_one(
        {"_id": ObjectId("68d45dd062efa1978c6b854a")}
    )

    update_response = client.put(
        "/space-schedules/update",
        json={
            "schedule_id": "68d45dd062efa1978c6b854a",
            "space_id": "68a36894e6decd139abbe089",
            # action time is unchanged
        },
        headers={"Authorization": "Bearer token"},
    )

    assert update_response.status_code == 200
    json = update_response.json()
    assert isinstance(json, dict)
    assert "message" in json
    assert json["message"] == "Updated space schedule"

    schedule_after_update = dbp.space_schedule.find_one(
        {"_id": ObjectId("68d45dd062efa1978c6b854a")}
    )
    assert schedule_before_update["_id"] == schedule_after_update["_id"]
    assert schedule_before_update["action_time"] == schedule_after_update["action_time"]
    assert schedule_after_update["space_id"] == ObjectId("68a36894e6decd139abbe089")


def test_update_space_schedule_as_liaison_unauthorized(dbp, fake_auth):
    """It should fail to update a space schedule that was not created by the user"""
    app.dependency_overrides[get_authorization] = override_get_authorization_liaison

    update_response = client.put(
        "/space-schedules/update",
        json={
            "schedule_id": "68d45dd062efa1978c6b8549",
            "space_id": "68a36894e6decd139abbe089",
            # action time is unchanged
        },
        headers={"Authorization": "Bearer token"},
    )

    assert update_response.status_code == 400
    assert isinstance(update_response.json(), dict)
    assert "detail" in update_response.json()
    assert update_response.json()["detail"] == "Could not find space schedule"


def test_delete_space(dbp, fake_auth):
    """It should handle a delete request"""
    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    assert dbp.space_schedule.count_documents({}) == 3

    delete_response = client.delete(
        "/space-schedules/delete",
        params={"schedule_id": "68d45dd062efa1978c6b8549"},
        headers={"Authorization": "Bearer token"},
    )

    assert delete_response.status_code == 200
    json = delete_response.json()
    assert isinstance(json, dict)
    assert "message" in json
    assert json["message"] == "Deleted space schedule"
    assert dbp.space_schedule.count_documents({}) == 2


def test_delete_nonexistant_space(dbp, fake_auth):
    """It should fail to delete a schedule that doesn't exist"""
    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    assert dbp.space_schedule.count_documents({}) == 3

    delete_response = client.delete(
        "/space-schedules/delete",
        params={"schedule_id": "68d45dd062efa1978c6b8541"},
        headers={"Authorization": "Bearer token"},
    )

    assert delete_response.status_code == 400
    json = delete_response.json()
    assert isinstance(json, dict)
    assert "detail" in json
    assert json["detail"] == "Not able to delete space schedule"
    assert dbp.space_schedule.count_documents({}) == 3


def test_delete_space_as_liaison(dbp, fake_auth):
    """It should only delete schedules created by the user"""
    app.dependency_overrides[get_authorization] = override_get_authorization_liaison

    assert dbp.space_schedule.count_documents({}) == 3

    # should succeed
    delete_response = client.delete(
        "/space-schedules/delete",
        params={"schedule_id": "68d45dd062efa1978c6b854a"},
        headers={"Authorization": "Bearer token"},
    )
    assert delete_response.status_code == 200
    json = delete_response.json()
    assert isinstance(json, dict)
    assert "message" in json
    assert json["message"] == "Deleted space schedule"
    assert dbp.space_schedule.count_documents({}) == 2

    # should fail
    delete_response = client.delete(
        "/space-schedules/delete",
        params={"schedule_id": "68d45dd062efa1978c6b8549"},
        headers={"Authorization": "Bearer token"},
    )
    assert delete_response.status_code == 400
    assert delete_response.json()["detail"] == "Not able to delete space schedule"
    assert dbp.space_schedule.count_documents({}) == 2
