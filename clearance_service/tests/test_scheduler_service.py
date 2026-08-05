"""Tests for Validation Assignment controller"""

from datetime import datetime, timedelta, timezone

from bson import ObjectId
from fastapi.testclient import TestClient
from main import app

from clearance_service.models import acs
from clearance_service.models.audit import Audit
from clearance_service.models.clearance import Clearance
from clearance_service.models.personnel import Personnel
from clearance_service.models.scheduled_action import ScheduledAction
from clearance_service.util.scheduler_service import SchedulerService
from clearance_service.util.settings import (
    SCHEDULED_ACTION_PURGE_CUTOFF,
    SCHEDULER_LIMIT,
)

client = TestClient(app)
now = datetime.now(timezone.utc)
past_actions = [
    {
        "assigner_email": "guy@test.email",
        "assigner_name": "Guy Test",
        "assignee_email": "person1@email.com",
        "clearance_id": 10354,
        "action": "assign",
        "action_time": now - timedelta(days=9),
        "submitted_time": now,
        "status": "pending",
    },
    {
        "assigner_email": "guy@test.email",
        "assigner_name": "Guy Test",
        "assignee_email": "person2@email.com",
        "clearance_id": 10353,
        "action": "revoke",
        "action_time": now - timedelta(days=9),
        "submitted_time": now,
        "status": "pending",
    },
    {
        "assigner_email": "guy@test.email",
        "assigner_name": "Guy Test",
        "assignee_email": "person1@email.com",
        "clearance_id": 10353,
        "action": "revoke",
        "action_time": now - timedelta(days=9),
        "submitted_time": now,
        "status": "pending",
    },
    {
        "assigner_email": "guy@test.email",
        "assigner_name": "Guy Test",
        "assignee_email": "person1@email.com",
        "clearance_id": 10355,
        "action": "revoke",
        "action_time": now - timedelta(days=9),
        "submitted_time": now,
        "status": "pending",
    },
]


def mock_process(configs: list[ScheduledAction.ActionConfig], **kwargs):
    """Mock assigning clearances"""
    succeeded_actions = {}
    for config in configs:
        assignee_email = config.assignee_email or None
        clearance_id = config.clearance_id or None

        if succeeded_actions.get(assignee_email) is None:
            succeeded_actions[assignee_email] = {}
        succeeded_actions[assignee_email][clearance_id] = True
    return {
        "succeeded": succeeded_actions,
        "failed": {},
        "already_completed": {},
        "pending": [],
    }


def test_update_action_statuses(dbp, fake_auth, monkeypatch, time_machine):
    """It should update the status of actions that have been processed."""

    time_machine.move_to(datetime(now.year, 8, 15, tzinfo=timezone.utc))
    monkeypatch.setattr(Audit, "add_many", lambda *_, **__: [])
    monkeypatch.setattr(
        acs.personnel,
        "search",
        lambda *_, **__: [
            {
                "FirstName": "testfirst",
                "MiddleName": "testmiddle",
                "LastName": "testlast",
                "EmailAddress": "testemail@test.email",
                "ObjectID": 5000,
                "Disabled": False,
            },
        ],
    )
    monkeypatch.setattr(
        Personnel,
        "search_by_email",
        lambda *_, **__: [
            Personnel(
                {"FirstName": "firstname", "EmailAddress": "person2@email.com", "ObjectID": 5000},
            )
        ],
    )
    monkeypatch.setattr(
        acs.clearance,
        "search",
        lambda *_, **__: [
            {"ObjectID": 6000, "Name": "Clearance0"},
            {"ObjectID": 6001, "Name": "Clearance1"},
            {"ObjectID": 6002, "Name": "Clearance2"},
            {"ObjectID": 6003, "Name": "Clearance3"},
            {"ObjectID": 6004, "Name": "Clearance4"},
            {"ObjectID": 6005, "Name": "Clearance5"},
        ],
    )
    monkeypatch.setattr(
        acs.action.personnel,
        "get_assigned_clearances",
        lambda *_, **__: [{"ClearanceID": 6001, "Name": "Clearance1"}],
    )
    monkeypatch.setattr(
        acs.action.personnel,
        "assign_clearances",
        lambda *_, **__: None,
    )

    assert dbp.scheduled_action.count_documents({}) == 8
    assert dbp.scheduled_action.count_documents({"status": "pending"}) == 7
    assert dbp.scheduled_action.count_documents({"status": "already_completed"}) == 1

    SchedulerService.push_to_ccure()

    assert dbp.scheduled_action.count_documents({}) == 8
    # the two future actions are still pending:
    assert dbp.scheduled_action.count_documents({"status": "pending"}) == 2
    # the one valid assignment succeeded:
    assert dbp.scheduled_action.count_documents({"status": "succeeded"}) == 1
    # one action already had 'already_completed', three pending actions updated their status:
    assert dbp.scheduled_action.count_documents({"status": "already_completed"}) == 4

    monkeypatch.undo()


def test_push_to_ccure_skips_malformed_documents(db, monkeypatch):
    """A document missing required ActionConfig fields (e.g. a pre-migration
    document with `assignee_id` but no `assignee_email`) should be marked
    failed instead of crashing the whole batch."""
    monkeypatch.setattr(SchedulerService, "scheduled_action_coll", db.scheduled_action)
    monkeypatch.setattr(Audit, "add_many", lambda *_, **__: [])
    monkeypatch.setattr(
        acs.personnel,
        "search",
        lambda *_, **__: [
            {
                "FirstName": "testfirst",
                "MiddleName": "testmiddle",
                "LastName": "testlast",
                "EmailAddress": "guy@test.email",
                "ObjectID": 5000,
                "Disabled": False,
            },
        ],
    )
    monkeypatch.setattr(
        Personnel,
        "search_by_email",
        lambda *_, **__: [
            Personnel(
                {"FirstName": "firstname", "EmailAddress": "person1@email.com", "ObjectID": 5001}
            ),
        ],
    )
    monkeypatch.setattr(
        acs.clearance,
        "search",
        lambda *_, **__: [{"ObjectID": 10354, "Name": "Clearance0"}],
    )
    monkeypatch.setattr(
        acs.action.personnel,
        "get_assigned_clearances",
        lambda *_, **__: [],
    )
    monkeypatch.setattr(
        acs.action.personnel,
        "assign_clearances",
        lambda *_, **__: None,
    )

    valid_action_id = ObjectId()
    malformed_action_id = ObjectId()
    db.scheduled_action.insert_many(
        [
            {
                "_id": valid_action_id,
                "assigner_email": "guy@test.email",
                "assigner_name": "Guy Test",
                "assignee_email": "person1@email.com",
                "clearance_id": 10354,
                "action": "assign",
                "action_time": now - timedelta(days=9),
                "submitted_time": now,
                "status": "pending",
            },
            {
                # legacy pre-migration document: no assignee_email
                "_id": malformed_action_id,
                "assigner_email": "guy@test.email",
                "assigner_name": "Guy Test",
                "assignee_id": "001132807",
                "clearance_id": 10355,
                "action": "assign",
                "action_time": now - timedelta(days=9),
                "submitted_time": now,
                "status": "pending",
            },
        ]
    )

    SchedulerService.push_to_ccure()

    malformed_doc = db.scheduled_action.find_one({"_id": malformed_action_id})
    assert malformed_doc["status"] == "failed"
    assert "error_message" in malformed_doc

    valid_doc = db.scheduled_action.find_one({"_id": valid_action_id})
    assert valid_doc["status"] == "succeeded"

    monkeypatch.undo()


def test_get_all_past_scheduled_actions(db, monkeypatch):
    """It should be able to get all scheduled actions"""
    monkeypatch.setattr(SchedulerService, "scheduled_action_coll", db.scheduled_action)

    now = datetime.now(timezone.utc)
    assignments = [
        {
            "assigner_email": "guy@test.email",
            "assigner_email": 5000,
            "assigner_name": "Guy Test",
            "assignee_email": "person1@email.com",
            "clearance_id": 10354,
            "action": "assign",
            "action_time": now - timedelta(days=9),
            "submitted_time": now,
            "status": "pending",
        },
        {
            "assigner_email": "guy@test.email",
            "assigner_email": 5000,
            "assigner_name": "Guy Test",
            "assignee_email": "person2@email.com",
            "clearance_id": 10353,
            "action": "revoke",
            "action_time": now - timedelta(days=9),
            "submitted_time": now,
            "status": "pending",
        },
        {
            "assigner_email": "guy@test.email",
            "assigner_email": 5000,
            "assigner_name": "Guy Test",
            "assignee_email": "person1@email.com",
            "clearance_id": 10353,
            "action": "revoke",
            "action_time": now - timedelta(days=9),
            "submitted_time": now,
            "status": "pending",
        },
        {
            "assigner_email": "guy@test.email",
            "assigner_email": 5000,
            "assigner_name": "Guy Test",
            "assignee_email": "person1@email.com",
            "clearance_id": 10355,
            "action": "revoke",
            "action_time": now - timedelta(days=9),
            "submitted_time": now,
            "status": "pending",
        },
    ]

    db.scheduled_action.insert_many(assignments)

    results = SchedulerService.get_scheduled_actions()
    assert len(results) == 4

    monkeypatch.undo()


def test_skip_future_scheduled_actions(db, monkeypatch):
    """It should not retrieve actions that are scheduled for the future"""
    monkeypatch.setattr(SchedulerService, "scheduled_action_coll", db.scheduled_action)

    assignment = {
        "assigner_email": "guy@test.email",
        "assigner_email": 5000,
        "assigner_name": "Guy Test",
        "assignee_email": "person1@email.com",
        "clearance_id": 10355,
        "action": "revoke",
        "action_time": now + timedelta(days=9),
        "submitted_time": now,
        "status": "pending",
    }

    db.scheduled_action.insert_one(assignment)

    results = SchedulerService.get_scheduled_actions()

    assert len(results) == 0

    monkeypatch.undo()


def test_purge_scheduled_actions(db, monkeypatch, caplog):
    """It should purge actions older than x days"""
    monkeypatch.setattr(SchedulerService, "scheduled_action_coll", db.scheduled_action)

    purge_cutoff_days = SCHEDULED_ACTION_PURGE_CUTOFF
    assignments = [
        {
            # successful revocation. purge it.
            "assigner_email": "dummy@email.com",
            "assigner_email": "person2@email.com",
            "assigner_name": "Dummy Guy",
            "assignee_email": "person2@email.com",
            "clearance_id": 6003,
            "action": "revoke",
            "action_time": now - timedelta(days=purge_cutoff_days + 3),
            "submitted_time": now,
            "status": "succeeded",
        },
        {
            # failed revocation. purge it.
            "assigner_email": "dummy@email.com",
            "assigner_email": "person2@email.com",
            "assigner_name": "Dummy Guy",
            "assignee_email": "person2@email.com",
            "clearance_id": 6003,
            "action": "revoke",
            "action_time": now - timedelta(days=purge_cutoff_days + 3),
            "submitted_time": now,
            "status": "failed",
        },
        {
            # already_completed assignment. purge it.
            "assigner_email": "dummy@email.com",
            "assigner_email": "person2@email.com",
            "assigner_name": "Dummy Guy",
            "assignee_email": "person2@email.com",
            "clearance_id": 6003,
            "action": "assign",
            "action_time": now - timedelta(days=purge_cutoff_days + 3),
            "submitted_time": now,
            "status": "already_completed",
        },
        {
            # recent successful revocation. keep it.
            "assigner_email": "dummy@email.com",
            "assigner_email": "person2@email.com",
            "assigner_name": "Dummy Guy",
            "assignee_email": "person2@email.com",
            "clearance_id": 6003,
            "action": "revoke",
            "action_time": now - timedelta(days=purge_cutoff_days - 3),
            "submitted_time": now,
            "status": "succeeded",
        },
        {
            # pending revocation. keep it.
            "assigner_email": "dummy@email.com",
            "assigner_email": "person2@email.com",
            "assigner_name": "Dummy Guy",
            "assignee_email": "person2@email.com",
            "clearance_id": 6003,
            "action": "revoke",
            "action_time": now + timedelta(days=3),
            "submitted_time": now,
            "status": "pending",
        },
    ]

    db.scheduled_action.insert_many(assignments)
    assert db.scheduled_action.count_documents({}) == 5

    SchedulerService.purge_scheduled_actions()

    assert db.scheduled_action.count_documents({}) == 2
    assert (
        f"Purging scheduled_action documents processed more than {purge_cutoff_days} days ago"
        in caplog.text
    )
    assert "Purged 3 documents from scheduled_action" in caplog.text

    monkeypatch.undo()


def test_scheduler_limit(db, monkeypatch):
    """It should only process the configured number of future actions on each run"""
    monkeypatch.setattr(SchedulerService, "scheduled_action_coll", db.scheduled_action)
    monkeypatch.setattr(ScheduledAction, "process", mock_process)

    total_action_count = SCHEDULER_LIMIT + 3
    actions = [dict(past_actions[0]) for _ in range(total_action_count)]

    for action in actions:
        action.pop("_id", 0)
    db.scheduled_action.insert_many(actions)
    docs = db.scheduled_action.find({"status": "pending"})
    assert len(list(docs)) == total_action_count

    for action in actions:
        action.pop("_id", 0)
    SchedulerService.push_to_ccure()
    docs = db.scheduled_action.find({"status": "pending"})
    assert len(list(docs)) == 3

    for action in actions:
        action.pop("_id", 0)
    SchedulerService.push_to_ccure()
    docs = db.scheduled_action.find({"status": "pending"})
    assert len(list(docs)) == max((3 - SCHEDULER_LIMIT, 0))


def test_update_liaison_clearance_names(db, monkeypatch):
    """It should update `liaison` clearance names that have been changed"""
    monkeypatch.setattr(SchedulerService, "liaison_coll", db["liaison"])
    monkeypatch.setattr(
        Clearance,
        "get_all",
        lambda *_, **__: {
            5000: {"name": "New Clearance Name", "id": 5000},
            5001: {"name": "Clearance A", "id": 5001},
        },
    )

    liaisons = [
        {
            "email": "person2@email.com",
            "clearances": [
                {
                    "name": "Old Clearance Name",
                    "id": 5000,
                },
                {
                    "name": "Clearance A",
                    "id": 5001,
                },
            ],
        }
    ]
    db["liaison"].insert_many(liaisons)

    stored_liaisons = list(db["liaison"].find({"email": "person2@email.com"}))
    assert len(stored_liaisons) == 1
    liaison = stored_liaisons[0]
    assert len(liaison["clearances"]) == 2
    stored_clearance_names = [clearance["name"] for clearance in liaison["clearances"]]
    assert "New Clearance Name" not in stored_clearance_names
    assert "Old Clearance Name" in stored_clearance_names
    assert "Clearance A" in stored_clearance_names

    SchedulerService.update_liaison_clearance_names()

    stored_liaisons = list(db["liaison"].find({"email": "person2@email.com"}))
    assert len(stored_liaisons) == 1
    liaison = stored_liaisons[0]
    assert len(liaison["clearances"]) == 2
    stored_clearance_names = [clearance["name"] for clearance in liaison["clearances"]]
    assert "New Clearance Name" in stored_clearance_names
    assert "Old Clearance Name" not in stored_clearance_names
    assert "Clearance A" in stored_clearance_names

    monkeypatch.undo()
