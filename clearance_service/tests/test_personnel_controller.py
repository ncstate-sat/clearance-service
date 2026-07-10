"""Tests for the personnel endpoints"""

from fastapi.testclient import TestClient
from main import app

from clearance_service.models.personnel import Personnel
from clearance_service.tests.override_get_authorization import override_get_authorization_admin
from clearance_service.util.authorization import get_authorization

app.dependency_overrides[get_authorization] = override_get_authorization_admin
client = TestClient(app)


def test_search_personnel(db, fake_auth, monkeypatch):
    """It should be able to search for personnel."""

    def mock_search(*_):
        return [
            Personnel({
                "FirstName": "John",
                "MiddleName": "Tyler",
                "LastName": "Champion",
                "EmailAddress": "jtchampi@test.biz",
            }),
            Personnel({
                "FirstName": "Lisa",
                "MiddleName": None,
                "LastName": "Moose",
                "EmailAddress": "lmoose@test.co.uk",
            }),
        ]

    monkeypatch.setattr(Personnel, "search", mock_search)

    response = client.post(
        "/personnel",
        json={
            "search": "marina",
            "search_fields": {
                "FirstName": "fuzz",
                "Text99": "fuzz",
            }
        },
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200
    json = response.json()
    assert "personnel" in json
    assert isinstance(json["personnel"], list)


def test_search_personnel_no_results(db, fake_auth, monkeypatch):
    """It should be able to run a search that gets no results back"""

    def mock_search(*_):
        return []

    monkeypatch.setattr(Personnel, "search", mock_search)

    response = client.post(
        "/personnel",
        json={
            "search": "marina",
            "search_fields": {
                "FirstName": "fuzz",
                "Text99": "fuzz",
            }
        },
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200
    json = response.json()
    assert "personnel" in json
    assert isinstance(json["personnel"], list)


def test_search_personnel_bulk(db, fake_auth, monkeypatch):
    """It should be able to search for a list of multiple people."""

    monkeypatch.setattr(Personnel, "search_by_email", lambda *_: [
        Personnel({
            "FirstName": "John",
            "MiddleName": "Tyler",
            "LastName": "Champion",
            "EmailAddress": "jtchampi@test.biz",
        }),
        Personnel({
            "FirstName": "Lisa",
            "MiddleName": None,
            "LastName": "Moose",
            "EmailAddress": "lmoose@test.co.uk",
        }),
    ])

    response = client.post(
        "/personnel/bulk",
        json={"emails": ["jtchampi@test.biz", "lmoose@test.co.uk", "notexist"]},
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200
    json = response.json()
    assert "personnel" in json
    assert isinstance(json["personnel"], list)
    assert "not_found" in json
    assert isinstance(json["not_found"], list)
    assert len(json["personnel"]) == 2
    assert len(json["not_found"]) == 1
