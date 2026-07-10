"""Tests for the liaison endpoints"""

from datetime import datetime, timezone

from fastapi.testclient import TestClient
from main import app

from clearance_service.models import acs
from clearance_service.models.clearance import Clearance
from clearance_service.models.door import Door
from clearance_service.models.door_group import DoorGroup
from clearance_service.models.personnel import Personnel
from clearance_service.tests.override_get_authorization import (
    override_get_authorization_admin,
    override_get_authorization_liaison,
)
from clearance_service.util.authorization import get_authorization
from clearance_service.util.handle_requests import RequestException

app.dependency_overrides[get_authorization] = override_get_authorization_admin
client = TestClient(app)

now = datetime.now(timezone.utc)


def mock_get_clearance_name(clearance_id):
    """Mock getting a clearance name by ID"""
    return f"Mocked Clearance ({clearance_id})"


def mock_search_personnel(terms, search_filter, page_size):
    """Mock searching personnel"""
    return [
        {
            "FirstName": "Liaison",
            "MiddleName": "",
            "LastName": "ToAdd",
            "EmailAddress": "liaison-to-add@test.edu",
            "ObjectID": "5000",
            "Disabled": True,
        }
    ]


def mock_search_credentials(terms, search_filter, page_size):
    """Mock searching credentials"""
    return []


def mock_get_by_ids(*_, **__):
    """Mock Clearance.get_by_ids"""
    return [{"id": 5000, "name": "Mock clearance"}]


def mock_find_one(*_, **__):
    """Mock Personnel.find_one"""
    return Personnel({
        "FirstName": "first",
        "MiddleName": "M",
        "LastName": "last",
        "EmailAddress": "test@email.com",
    })


def mock_error(*_, **__):
    """Mock Request Exception"""
    raise RequestException(400, "Bad request")


def test_error_revoke_liaison_permissions(db, fake_auth, monkeypatch):
    """
    The mocked "revoke_liaison_permissions" function should raise an error.
    It should catch the error thrown by the mocked function.
    """
    monkeypatch.setattr(Personnel, "find_one", mock_error)

    response = client.post(
        "/liaison/revoke",
        json={"email": "test1@email.com", "clearance_ids": [5000]},
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 400


def test_assign_liaison_permissions(db, fake_auth, monkeypatch):
    """
    It should be able to fetch liaison permissions for an individual.
    It should not fail if the permission was already assigned.
    """
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_by_ids)
    monkeypatch.setattr(Personnel, "find_one", mock_find_one)

    response1 = client.post(
        "/liaison/assign",
        json={"email": "test1@email.com", "clearance_ids": [5000]},
        headers={"Authorization": "Bearer token"},
    )
    response2 = client.post(
        "/liaison/assign",
        json={"email": "test1@email.com", "clearance_ids": [5000]},
        headers={"Authorization": "Bearer token"},
    )

    expected_json = {
        "record": {
            "email": "test1@email.com",
            "clearances": [
                {
                    "id": 5000,
                    "name": "Mock clearance",
                }
            ],
            "email": "test@email.com",
        }
    }
    assert response1.status_code == 200
    assert response1.json() == expected_json
    assert response2.status_code == 200
    assert response2.json() == expected_json


def test_assign_error(db, fake_auth, monkeypatch):
    """
    It should be able to fetch liaison permissions for an individual.
    It should not fail if the permission was already assigned.
    """
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_by_ids)
    monkeypatch.setattr(Personnel, "find_one", mock_error)

    response = client.post(
        "/liaison/assign",
        json={"email": "test1@email.com", "clearance_ids": [5000]},
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 400
    json = response.json()
    assert len(json) == 2
    assert json["detail"] == "Could not assign permissions"


def test_revoke_liaison_permissions(db, fake_auth, monkeypatch):
    """
    It should be able to fetch liaison permissions for an individual.
    It should not fail if the permission was not present.
    """

    monkeypatch.setattr(Personnel, "find_one", mock_find_one)

    response1 = client.post(
        "/liaison/revoke",
        json={"email": "test1@email.com", "clearance_ids": [5000]},
        headers={"Authorization": "Bearer token"},
    )
    response2 = client.post(
        "/liaison/revoke",
        json={"email": "test1@email.com", "clearance_ids": [5000]},
        headers={"Authorization": "Bearer token"},
    )

    expected_json = {
        "record": {"email": "test1@email.com", "clearances": [], "email": "test@email.com"}
    }
    assert response1.status_code == 200
    assert response1.json() == expected_json
    assert response2.status_code == 200
    assert response2.json() == expected_json


def test_get_liaison_permissions_without_data(db, fake_auth, monkeypatch):
    """
    It should be able to fetch liaison permissions for an individual.
    """

    response = client.get(
        "/liaison?email=test1@email.com",
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200


def test_get_liaison_permissions_with_data(db, fake_auth, monkeypatch):
    """
    It should be able to fetch liaison permissions for an individual.
    """
    monkeypatch.setattr(acs.clearance, "get_property", mock_get_clearance_name)
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_by_ids)
    monkeypatch.setattr(Personnel, "find_one", mock_find_one)

    client.post(
        "/liaison/assign",
        json={"email": "test@email.com", "clearance_ids": [5000]},
        headers={"Authorization": "Bearer token"},
    )
    get_response = client.get(
        "/liaison?email=test@email.com", headers={"Authorization": "Bearer token"}
    )

    expected_json = {
        "clearances": [
            {
                "id": 5000,
                "name": "Mock clearance",
            }
        ]
    }
    assert get_response.status_code == 200
    assert get_response.json() == expected_json


def test_liaison_needs_acknowledgement(dbp, time_machine):
    """It should require a new acknowledgement unless a valid acknowledgement already exists."""
    app.dependency_overrides[get_authorization] = override_get_authorization_liaison
    time_machine.move_to(datetime(now.year, 8, 15, tzinfo=timezone.utc))

    # where last_acknowledged doesn't exist
    response = client.get(
        "/liaison/needs-acknowledgement",
        headers={"Authorization": "Bearer token1"},
    )
    assert response.status_code == 200
    assert response.json().get("needs_acknowledgement") is True

    # where last_acknowledged is None
    response = client.get(
        "/liaison/needs-acknowledgement",
        headers={"Authorization": "Bearer token2"},
    )
    assert response.status_code == 200
    assert response.json().get("needs_acknowledgement") is True

    # where last_acknowledged is expired
    response = client.get(
        "/liaison/needs-acknowledgement",
        headers={"Authorization": "Bearer token3"},
    )
    assert response.status_code == 200
    assert response.json().get("needs_acknowledgement") is True

    # where last_acknowledged is still valid
    response = client.get(
        "/liaison/needs-acknowledgement",
        headers={"Authorization": "Bearer token4"},
    )
    assert response.status_code == 200
    assert response.json().get("needs_acknowledgement") is False

    # where the liaison is absent from the database
    response = client.get(
        "/liaison/needs-acknowledgement",
        headers={"Authorization": "Bearer token5"},
    )
    assert response.status_code == 200
    assert response.json().get("needs_acknowledgement") is True


def test_save_acknowledgement(dbp, fake_auth):
    """It should save a new timestamp for last_acknowledged."""
    # save a new role acknowledgement
    response = client.put(
        "/liaison/save-acknowledgement",
        headers={"Authorization": "Bearer token1"},
    )
    assert response.status_code == 200
    assert response.json().get("updated") == 1

    # check the liaison record
    response = client.get(
        "/liaison/needs-acknowledgement",
        headers={"Authorization": "Bearer token1"},
    )
    assert response.json().get("needs_acknowledgement") is False


def test_assign_no_clearance_permissions(db, fake_auth, monkeypatch):
    """
    It should respond with an error if a request is made to assign an empty array of clearances.
    """
    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    response = client.post(
        "/liaison/assign",
        headers={"Authorization": "Bearer token"},
        json={"email": "test2@email.com", "clearance_ids": []},
    )
    assert response.status_code == 400
    assert response.json()["detail"] == "At least one clearance is required to assign a clearance."


def test_add_liaison(db, fake_auth, monkeypatch):
    """
    It should add a liaison to the database.
    """
    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    monkeypatch.setattr(acs.personnel, "search", mock_search_personnel)
    monkeypatch.setattr(acs.credential, "search", mock_search_credentials)

    liaison_collection = db.liaison
    assert liaison_collection.count_documents({}) == 0

    response = client.post(
        "/liaison/add",
        headers={"Authorization": "Bearer token"},
        json={"email": "liaison-to-add@test.edu"},
    )
    assert response.status_code == 201
    assert response.json()["updated"] == {
        "first_name": "Liaison",
        "middle_name": "",
        "last_name": "ToAdd",
        "email": "liaison-to-add@test.edu",
        "acs_id": "5000",
        "active": False,
    }
    assert liaison_collection.count_documents({}) == 1


def test_add_existing_liaison(db, fake_auth, monkeypatch):
    """
    It should not add a duplicate liaison when adding a liaison already in the database.
    """
    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    monkeypatch.setattr(acs.credential, "search", mock_search_credentials)
    monkeypatch.setattr(acs.personnel, "search", mock_search_personnel)

    liaison_collection = db.liaison
    liaison_records = [
        {
            "liaison_id": "liaison-to-add",
            "email": "liaison-to-add@test.edu",
            "clearances": [],
        }
    ]
    liaison_collection.insert_many(liaison_records)
    assert liaison_collection.count_documents({}) == 1

    response = client.post(
        "/liaison/add",
        headers={"Authorization": "Bearer token"},
        json={"email": "liaison-to-add@test.edu"},
    )
    assert response.status_code == 200
    assert response.json()["updated"] == {"email": "liaison-to-add@test.edu"}
    assert liaison_collection.count_documents({}) == 1


def test_remove_liaison(db, fake_auth, monkeypatch):
    """
    It should remove a liaison from the database.
    """
    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    liaison_collection = db.liaison
    liaison_records = [
        {
            "liaison_id": "person1",
            "email": "person3@email.com",
            "clearances": [],
        }
    ]
    liaison_collection.insert_many(liaison_records)

    response = client.post(
        "/liaison/remove",
        headers={"Authorization": "Bearer token"},
        json={"email": "person3@email.com"},
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 1


def test_remove_liaison_with_no_record(db, fake_auth, monkeypatch):
    """
    It should not remove a liaison who doesn't exist.
    """
    app.dependency_overrides[get_authorization] = override_get_authorization_admin

    response = client.post(
        "/liaison/remove",
        headers={"Authorization": "Bearer token"},
        json={"email": "liaison-does-not-exist@test.edu"},
    )
    assert response.status_code == 200
    assert response.json()["updated"] == 0


def test_get_doors(db, fake_auth, monkeypatch):
    """It should show a liaison's assignable doors"""
    app.dependency_overrides[get_authorization] = override_get_authorization_admin
    monkeypatch.setattr(
        Personnel,
        "get_doors",
        lambda *_, **__: [
            Door(4000, "fakedoor0"),
            Door(4001, "fakedoor1"),  # also appears in the door group, that's fine
            Door(4003, "zzz_fakedoor3"),
            DoorGroup(4000, "fakedoorgroup0"),
        ],
    )

    response = client.get(
        "/liaison/doors",
        headers={"Authorization": "Bearer token"},
    )
    assert response.status_code == 200
    json = response.json()
    assert isinstance(json, list)
    assert len(json) == 4
    door_group = json[2]  # they should be sorted by name
    assert door_group["type"] == "door group"
