import os
from datetime import datetime, timedelta, timezone

import pytest
from auth_checker import AuthChecker
from bson import ObjectId
from pymongo import ASCENDING, MongoClient

now = datetime.now(timezone.utc)

mongo_client = MongoClient(os.getenv("TEST_DB_URL"))
os.environ["CLEARANCE_DB_URL"] = os.environ["TEST_DB_URL"]


def setup_db():
    """Todo: Sanely handle the case where the server isn't running
    Currently mongo or PyMongo will happily return a MongoClient even
    if the server is offline. When an operation is attempted, it will
    hang without raising an exception.
    """


def tear_down_db():
    db = mongo_client.clearance_service
    for collection in db.list_collection_names():
        db.drop_collection(collection)


@pytest.fixture(autouse=True)
def before_and_after_test():
    setup_db()
    yield
    tear_down_db()


@pytest.fixture
def db():
    mongo_client.clearance_service.liaison.create_index(
        [("email", ASCENDING)], name="email_1", unique=True
    )
    return mongo_client.clearance_service


@pytest.fixture
def dbp(db):
    today = datetime(year=now.year, month=8, day=15, tzinfo=timezone.utc)
    db.audit.insert_many(
        [
            {
                "assigner": "person1",
                "assigner_email": "person1@email.com",
                "assignee": "person2",
                "assignee_email": "person2@email.com",
                "action": "ClearanceA activated",
                "clearance_id": 1234,
                "clearance_name": "ClearanceA",
                "timestamp": today - timedelta(days=31, hours=1),
            },
            {
                "assigner": "person1",
                "assigner_email": "person1@email.com",
                "assignee": "person2",
                "assignee_email": "person2@email.com",
                "action": "ClearanceA activated",
                "clearance_id": 1234,
                "clearance_name": "ClearanceA",
                "timestamp": today - timedelta(days=31, hours=2),
            },
            {
                "assigner": "person1",
                "assigner_email": "person1@email.com",
                "assignee": "person2",
                "assignee_email": "person2@email.com",
                "action": "ClearanceA activated",
                "clearance_id": 1234,
                "clearance_name": "ClearanceA",
                "timestamp": today - timedelta(days=500),
            },
            {
                "assigner": "person1",
                "assigner_email": "person1@email.com",
                "assignee": "person2",
                "assignee_email": "person2@email.com",
                "action": "ClearanceA activated",
                "clearance_id": 1234,
                "clearance_name": "ClearanceA",
                "timestamp": today - timedelta(days=75),
            },
            {
                "assigner": "person2",
                "assigner_email": "person2@email.com",
                "assignee": "person1",
                "assignee_email": "person1@email.com",
                "action": "ClearanceA activated",
                "clearance_id": 1234,
                "clearance_name": "ClearanceA",
                "timestamp": today - timedelta(days=31, hours=1),
            },
            {
                "assigner": "person2",
                "assigner_email": "person2@email.com",
                "assignee": "person1",
                "assignee_email": "person7@email.com",
                "action": "ClearanceA activated",
                "clearance_id": 1234,
                "clearance_name": "ClearanceA",
                "timestamp": today - timedelta(days=31, hours=1),
            },
        ]
    )
    db["liaison"].insert_many(
        [
            {
                "liaison_id": "person1",
                "email": "person1@email.com",
                "clearances": [],
            },
            {
                "liaison_id": "person2",
                "email": "person2@email.com",
                "clearances": [],
            },
            {
                "liaison_id": "person3",
                "email": "person3@email.com",
                "clearances": [],
            },
            {
                "liaison_id": "person4",
                "email": "person4@email.com",
                "clearances": [],
            },
        ]
    )
    db.scheduled_action.insert_many(
        [
            {
                # future assignment
                "_id": ObjectId("64625661a3f03b7bcddf2130"),
                "assigner_email": "person2@email.com",
                "assigner_name": "Dummy Guy",
                "assignee_email": "person2@email.com",
                "clearance_id": 6000,
                "action": "assign",
                "action_time": today + timedelta(days=10),
                "submitted_time": now,
                "status": "pending",
            },
            {
                # future assignment
                "_id": ObjectId("64625661a3f03b7bcddf2131"),
                "assigner_email": "person2@email.com",
                "assigner_name": "Dummy Guy",
                "assignee_email": "GAperson2@email.com",
                "clearance_id": 6005,
                "action": "assign",
                "action_time": today + timedelta(days=3),
                "submitted_time": now,
                "status": "pending",
            },
            {
                # past assignment
                "_id": ObjectId("64625661a3f03b7bcddf2132"),
                "assigner_email": "person2@email.com",
                "assigner_name": "Dummy Guy",
                "assignee_email": "person2@email.com",
                "clearance_id": 6001,
                "action": "assign",
                "action_time": today - timedelta(days=10),
                "submitted_time": now,
                "status": "pending",
            },
            {
                # past assignment
                "_id": ObjectId("64625661a3f03b7bcddf2133"),
                "assigner_email": "person2@email.com",
                "assigner_name": "Dummy Guy",
                "assignee_email": "person2@email.com",
                "clearance_id": 6002,
                "action": "assign",
                "action_time": today - timedelta(days=10),
                "submitted_time": now,
                "status": "pending",
            },
            {
                # past assignment
                "_id": ObjectId("64625661a3f03b7bcddf2134"),
                "assigner_email": "person2@email.com",
                "assigner_name": "Dummy Guy",
                "assignee_email": "person2@email.com",
                "clearance_id": 6001,
                "action": "assign",
                "action_time": today - timedelta(days=10),
                "submitted_time": now,
                "status": "pending",
            },
            {
                # past revocation
                "_id": ObjectId("64625661a3f03b7bcddf2135"),
                "assigner_email": "person1@email.com",
                "assigner_name": "Dummy Guy",
                "assignee_email": "person2@email.com",
                "clearance_id": 6003,
                "action": "revoke",
                "action_time": today - timedelta(days=10),
                "submitted_time": now,
                "status": "pending",
            },
            {
                # already completed
                "_id": ObjectId("64625661a3f03b7bcddf2136"),
                "assigner_email": "person1@email.com",
                "assigner_name": "Dummy Guy",
                "assignee_email": "person2@email.com",
                "clearance_id": 6004,
                "action": "revoke",
                "action_time": today - timedelta(days=10),
                "submitted_time": now,
                "status": "already_completed",
            },
            {
                # already completed
                "_id": ObjectId("64625661a3f03b7bcddf2137"),
                "assigner_email": "person2@email.com",
                "assigner_name": "Dummy Guy",
                "assignee_email": "person2@email.com",
                "clearance_id": 6006,
                "action": "assign",
                "action_time": today - timedelta(days=10000),
                "submitted_time": now,
                "status": "pending",
            },
        ],
    )
    db["space"].insert_many(
        [
            {
                "_id": ObjectId("68a36894e6decd139abbe087"),
                "name": "testspace1",
                "door_ids": [5000],
                "created_on": now,
                "modified_on": now,
                "created_by": "testguy@email.gov",
            },
            {
                "_id": ObjectId("68a36894e6decd139abbe088"),
                "name": "testspace2",
                "door_ids": [5000, 5999],
                "created_on": now,
                "modified_on": now,
                "created_by": "testguy@email.gov",
            },
            {
                "_id": ObjectId("68a36894e6decd139abbe089"),
                "name": "testspace3",
                "door_ids": [],
                "created_on": now,
                "modified_on": now,
                "created_by": "test_user@test.edu",
            },
            {
                "_id": ObjectId("68a36894e6decd139abbe000"),
                "name": "other",
                "door_ids": [9999, 8888],
                "created_on": now,
                "modified_on": now,
                "created_by": "test_user@test.edu",
            },
        ]
    )
    db.space_schedule.insert_many(
        [
            {
                "_id": ObjectId("68d45dd062efa1978c6b8549"),
                "space_id": ObjectId("68a36894e6decd139abbe088"),  # testspace2
                "action_time": now,
                "action_type": "unlock",
                "series_name": "test_series1",
                "created_by": "rsemmle@test.edu",
                "created_on": now,
                "modified_on": now,
            },
            {
                "_id": ObjectId("68d45dd062efa1978c6b854a"),
                "space_id": ObjectId("68a36894e6decd139abbe087"),  # testspace1
                "action_time": now,
                "action_type": "lock",
                "series_name": "test_series1",
                "created_by": "test_user@test.edu",
                "created_on": now,
                "modified_on": now,
            },
            {
                "_id": ObjectId("68d45dd062efa1978c6b854b"),
                "space_id": ObjectId("68a36894e6decd139abbe088"),  # testspace2
                "action_time": now,
                "action_type": "lock",
                "series_name": "test_series2",
                "created_by": "test_user@test.edu",
                "created_on": now,
                "modified_on": now,
            },
        ]
    )
    return db


@pytest.fixture
def fake_auth(monkeypatch):
    monkeypatch.setattr(AuthChecker, "__call__", lambda _: True)
