"""Tests for the spaces endpoints"""

from datetime import datetime

from fastapi.testclient import TestClient
from main import app

from clearance_service.models.door import Door
from clearance_service.models.personnel import Personnel
from clearance_service.tests.override_get_authorization import (
    override_get_authorization_admin,
    override_get_authorization_liaison,
)
from clearance_service.util.authorization import get_authorization

client = TestClient(app)
now = datetime.now()


def test_create_space(db, fake_auth, monkeypatch):
    """It should correctly handle create requests"""
    app.dependency_overrides[get_authorization] = override_get_authorization_admin
    monkeypatch.setattr(
        Personnel,
        "get_doors_ungrouped",
        lambda *_, **__: {
            Door(5000, "mydoor1"),
        },
    )
    response = client.post(
        "/spaces/create",
        json={
            "name": "mydoor1",
            "door_ids": [5000],
        },
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 201
    json = response.json()
    assert isinstance(json, dict)
    assert "message" in json
    assert "Created new space" in json["message"]


def test_create_space_not_permitted(dbp, fake_auth, monkeypatch):
    """It should fail if the user adds a door they don't have  permission for"""
    app.dependency_overrides[get_authorization] = override_get_authorization_admin
    monkeypatch.setattr(
        Personnel,
        "get_doors_ungrouped",
        lambda *_, **__: {
            Door(5000, "mydoor1"),
        },
    )
    response = client.post(
        "/spaces/create",
        json={
            "name": "mydoor2",
            "door_ids": [5001],
        },
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 401
    json = response.json()
    assert isinstance(json, dict)
    assert "detail" in json
    assert "Not authorized" in json["detail"]


def test_search_spaces(dbp, fake_auth):
    """It should handle a search request"""
    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    response = client.get("/spaces/search", headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    json = response.json()
    assert isinstance(json, list)
    assert len(json) == 4
    space = json[0]
    assert isinstance(space, dict)
    assert len(space) == 6


def test_update_space(dbp, fake_auth, monkeypatch):
    """It should successfully update a space if the user has the right permissions"""
    app.dependency_overrides[get_authorization] = override_get_authorization_liaison

    monkeypatch.setattr(
        Personnel,
        "get_doors_ungrouped",
        lambda *_, **__: {
            Door(5000, "mydoor1"),
        },
    )

    response = client.put(
        "/spaces/update",
        json={
            "space_id": "68a36894e6decd139abbe089",
            "new_name": "mynewdoor1",
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 200
    json = response.json()
    assert isinstance(json, dict)
    assert "message" in json
    assert "Updated space" in json["message"]


def test_update_space_not_authorized(db, fake_auth, monkeypatch):
    """It should fail if the user tries to add a door they don't have permissions for"""
    app.dependency_overrides[get_authorization] = override_get_authorization_liaison

    monkeypatch.setattr(
        Personnel,
        "get_doors_ungrouped",
        lambda *_, **__: {
            Door(5000, "mydoor1"),
        },
    )

    response = client.put(
        "/spaces/update",
        json={
            "space_id": "68a36894e6decd139abbe089",
            "new_door_ids": [5000, 5001],
        },
        headers={"Authorization": "Bearer token"},
    )

    assert response.status_code == 401
    json = response.json()
    assert isinstance(json, dict)
    assert "detail" in json
    assert "Not authorized" in json["detail"]


def test_delete_space(dbp, fake_auth, monkeypatch):
    """It should handle a delete request if the user has the right permissions"""
    app.dependency_overrides[get_authorization] = override_get_authorization_liaison

    delete_response = client.delete(
        "/spaces/delete",
        params={"space_id": "68a36894e6decd139abbe089"},
        headers={"Authorization": "Bearer token"},
    )

    assert delete_response.status_code == 200
    json = delete_response.json()
    assert isinstance(json, dict)
    assert "message" in json
    assert "Deleted space" in json["message"]


def test_delete_space_failure(dbp, fake_auth):
    """It should provide the right error message if the delete request fails"""
    app.dependency_overrides[get_authorization] = override_get_authorization_liaison

    delete_response = client.delete(
        "/spaces/delete",
        params={"space_id": "68a36894e6decd139abbe088"},
        headers={"Authorization": "Bearer token"},
    )

    assert delete_response.status_code == 400
    json = delete_response.json()
    assert isinstance(json, dict)
    assert "detail" in json
    assert "Not able to delete" in json["detail"]
