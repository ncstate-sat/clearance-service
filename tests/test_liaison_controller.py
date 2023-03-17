"""Tests for the liaison endpoints"""

from fastapi.testclient import TestClient
from middleware.get_authorization import get_authorization
from tests.override_get_authorization import override_get_authorization
from main import app
from util.auth_checker import AuthChecker
from util.ccure_api import CcureApi


app.dependency_overrides[get_authorization] = override_get_authorization
client = TestClient(app)


def mock_check_authorization(*_, **__):
    """"Mock AuthChecker response"""
    return None


def mock_get_clearance_name(clearance_id):
    """Mock getting a clearance name by ID"""
    return f"Mocked Clearance ({clearance_id})"


def test_assign_liaison_permissions(monkeypatch):
    """
    It should be able to fetch liaison permissions for an individual.
    It should not fail if the permission was already assigned.
    """
    monkeypatch.setattr(AuthChecker, "check_authorization",
                        mock_check_authorization)

    response1 = client.post("/liaison/assign", json={
        "campus_id": "000101234",
        "clearance_ids": ["D6A233C5-7339-4461-A2DC-89BADD182F97"]
    }, headers={"Authorization": "Bearer token"})
    response2 = client.post("/liaison/assign", json={
        "campus_id": "000101234",
        "clearance_ids": ["D6A233C5-7339-4461-A2DC-89BADD182F97"]
    }, headers={"Authorization": "Bearer token"})

    expected_json = {
        "record": {
            "campus_id": "000101234",
            "clearance_ids": ["D6A233C5-7339-4461-A2DC-89BADD182F97"]
        }
    }

    assert response1.status_code == 200
    assert response1.json() == expected_json
    assert response2.status_code == 200
    assert response2.json() == expected_json


def test_revoke_liaison_permissions(monkeypatch):
    """
    It should be able to fetch liaison permissions for an individual.
    It should not fail if the permission was not present.
    """
    monkeypatch.setattr(AuthChecker, "check_authorization",
                        mock_check_authorization)

    response1 = client.post("/liaison/revoke", json={
        "campus_id": "000101234",
        "clearance_ids": ["D6A233C5-7339-4461-A2DC-89BADD182F97"]
    }, headers={"Authorization": "Bearer token"})
    response2 = client.post("/liaison/revoke", json={
        "campus_id": "000101234",
        "clearance_ids": ["D6A233C5-7339-4461-A2DC-89BADD182F97"]
    }, headers={"Authorization": "Bearer token"})

    expected_json = {
        "record": {
            "campus_id": "000101234",
            "clearance_ids": []
        }
    }

    assert response1.status_code == 200
    assert response1.json() == expected_json
    assert response2.status_code == 200
    assert response2.json() == expected_json


def test_get_liaison_permissions_without_data(monkeypatch):
    """
    It should be able to fetch liaison permissions for an individual.
    """
    monkeypatch.setattr(AuthChecker, "check_authorization",
                        mock_check_authorization)

    response = client.get("/liaison?campus_id=000101234", headers={
        "Authorization": "Bearer token"})
    assert response.status_code == 200


def test_get_liaison_permissions_with_data(monkeypatch):
    """
    It should be able to fetch liaison permissions for an individual.
    """
    monkeypatch.setattr(AuthChecker, "check_authorization",
                        mock_check_authorization)
    monkeypatch.setattr(CcureApi, "get_clearance_name",
                        mock_get_clearance_name)

    client.post("/liaison/assign", json={
        "campus_id": "000101234",
        "clearance_ids": ["D6A233C5-7339-4461-A2DC-89BADD182F97"]
    }, headers={"Authorization": "Bearer token"})
    get_response = client.get("/liaison?campus_id=000101234", headers={
        "Authorization": "Bearer token"})

    expected_json = {
        "clearances": [{
            "id": "D6A233C5-7339-4461-A2DC-89BADD182F97",
            "name": "Mocked Clearance (D6A233C5-7339-4461-A2DC-89BADD182F97)"
        }]
    }

    assert get_response.status_code == 200
    assert get_response.json() == expected_json
