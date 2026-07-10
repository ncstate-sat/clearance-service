"""Tests for the Clearance Assignment model"""
from datetime import datetime, timedelta, timezone

from acslib.ccure.base import CcureACS

from clearance_service.models import acs
from clearance_service.models.audit import Audit
from clearance_service.models.clearance import Clearance
from clearance_service.models.personnel import Personnel
from clearance_service.models.scheduled_action import ScheduledAction
from clearance_service.util.db_connect import get_clearance_collection

people_configs = [
    {
        "ProperName": "John Champion",
        "ObjectID": 5001,
        "Name": "Champion, John",
        "LastName": "Champion",
        "FirstName": "John",
        "MiddleName": "",
        "Disabled": False,
        "EmailAddress": "person1@email.com",
    },
    {
        "ProperName": "Lisa Mena",
        "ObjectID": 5004,
        "Name": "Mena, Lisa",
        "LastName": "Mena",
        "FirstName": "Lisa",
        "MiddleName": "",
        "Disabled": False,
        "EmailAddress": "person2@email.com",
    },
]
personnel = Personnel(people_configs[1])

clearances = [
    {"Name": "VRB-Test Clearance 1", "ObjectID": 6000},
    {"Name": "Another Test Clearance", "ObjectID": 6001},
    {"Name": "VRB-Test Clearance 2", "ObjectID": 6005},
    {"Name": "ClearanceAA", "ObjectID": 6006},
    {"Name": "ClearanceB", "ObjectID": 10354},
    {"Name": "ClearanceC", "ObjectID": 10355},
    {"Name": "VRB - HS - Test", "ObjectID": 9497},
]

clearance_assignments = [{"ClearanceID": c.get("ObjectID")} for c in clearances]


def mock_get_clearance_assignments(*_, **__):
    return [
        {
            "Name": "Clearance1",
            "ObjectID": 6929,
            "PersonnelID": 5004,
            "ClearanceID": 10354,
        },
        {
            "Name": "Clearance2",
            "ObjectID": 6930,
            "PersonnelID": 5004,
            "ClearanceID": 10355,
        },
    ]


def mock_get_clearances_by_id(ids: list[int], **kwargs):
    filtered_clearances = [
        clearance for clearance in clearances if clearance.get("ObjectID") in ids
    ]
    return [
        {"id": clearance["ObjectID"], "name": clearance["Name"]}
        for clearance in filtered_clearances
    ]


def mock_personnel_search(terms, *_, **__):
    """Mock acslib personnel search"""
    results = []
    if "person1@email.com" in terms:
        results.append(people_configs[0])
    if "person2@email.com" in terms:
        results.append(people_configs[1])
    return results


def test_process(db, fake_auth, monkeypatch):
    """Test assigning one clearance and revoking it at a later date."""
    monkeypatch.setattr(acs.personnel, "search", mock_personnel_search)
    monkeypatch.setattr(acs.action.personnel, "get_assigned_clearances", lambda *_, **__: [])
    monkeypatch.setattr(acs.action.personnel, "assign_clearances", lambda *_, **__: None)
    monkeypatch.setattr(Personnel, "search_by_email", lambda *_, **__: [personnel])
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_clearances_by_id)
    monkeypatch.setattr(Audit, "add_many", lambda *_, **__: [])

    ScheduledAction.process(
        configs=[
            ScheduledAction.ActionConfig(
                assigner_email="person1@email.com",
                assigner_name="John Champion",
                assignee_email="test1@email.com",
                clearance_id=9497,
                action="assign",
            ),
            ScheduledAction.ActionConfig(
                assigner_email="person1@email.com",
                assigner_name="John Champion",
                assignee_email="test1@email.com",
                clearance_id=9497,
                action="revoke",
                action_time=datetime.now(timezone.utc) + timedelta(days=5),
            ),
        ]
    )
    assert "This test passes if no exception is raised."


def test_process_with_start_and_end(db, fake_auth, monkeypatch):
    """Test assigning one clearance with a start and end date"""
    monkeypatch.setattr(acs.personnel, "search", mock_personnel_search)
    monkeypatch.setattr(acs.action.personnel, "get_assigned_clearances", lambda *_, **__: [])
    monkeypatch.setattr(acs.action.personnel, "assign_clearances", lambda *_, **__: None)
    monkeypatch.setattr(Personnel, "search_by_email", lambda *_, **__: [personnel])
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_clearances_by_id)
    monkeypatch.setattr(Audit, "add_many", lambda *_, **__: [])

    assert db.scheduled_action.count_documents({}) == 0

    ScheduledAction.process(
        configs=[
            ScheduledAction.ActionConfig(
                assigner_email="person1@email.com",
                assigner_name="John Champion",
                assignee_email="person2@email.com",
                clearance_id=9497,
                action="assign",
                action_time=datetime.now(timezone.utc) + timedelta(days=2),
            ),
            ScheduledAction.ActionConfig(
                assigner_email="person1@email.com",
                assigner_name="John Champion",
                assignee_email="person2@email.com",
                clearance_id=9497,
                action="revoke",
                action_time=datetime.now(timezone.utc) + timedelta(days=5),
            ),
        ]
    )
    assert db.scheduled_action.count_documents({}) == 2


def test_process_revoke(db, fake_auth, monkeypatch):
    """Test revoking one clearance"""
    monkeypatch.setattr(acs.personnel, "search", mock_personnel_search)
    monkeypatch.setattr(
        acs.action.personnel, "get_assigned_clearances", mock_get_clearance_assignments
    )
    monkeypatch.setattr(acs.action.personnel, "revoke_clearances", lambda *_, **__: 0)
    monkeypatch.setattr(Personnel, "search_by_email", lambda *_, **__: [personnel])
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_clearances_by_id)
    monkeypatch.setattr(Audit, "add_many", lambda *_, **__: [])

    result = ScheduledAction.process(
        configs=[
            ScheduledAction.ActionConfig(
                assigner_email="person1@email.com",
                assigner_name="John Champion",
                assignee_email="person2@email.com",
                clearance_id=10354,
                action="revoke",
            ),
        ]
    )
    assert result == {
        "succeeded": {
            "person2@email.com": {
                10354: True,
            }
        },
        "failed": {},
        "already_completed": {},
        "pending": [],
    }


def test_assign_invalid_clearances_and_assignees(db, fake_auth, monkeypatch, caplog):
    """It should assign the valid clearances and assignees and log the ones that don't exist"""
    monkeypatch.setattr(acs.personnel, "search", mock_personnel_search)
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_clearances_by_id)
    monkeypatch.setattr(acs.action.personnel, "get_assigned_clearances", lambda *_, **__: [])
    monkeypatch.setattr(acs.action.personnel, "assign_clearances", lambda *_, **__: None)
    monkeypatch.setattr(Personnel, "search_by_email", lambda *_, **__: [personnel])
    monkeypatch.setattr(Audit, "add_many", lambda *_, **__: [])

    result = ScheduledAction.process(
        configs=[
            ScheduledAction.ActionConfig(
                assigner_email="person1@email.com",
                assigner_name="John Champion",
                assignee_email="person2@email.com",  # exists
                clearance_id=10354,  # exists
                action="assign",
            ),
            ScheduledAction.ActionConfig(
                assigner_email="person1@email.com",
                assigner_name="John Champion",
                assignee_email="person2@email.com",  # exists
                clearance_id=10353,  # doesn't exist
                action="assign",
            ),
            ScheduledAction.ActionConfig(
                assigner_email="person1@email.com",
                assigner_name="John Champion",
                assignee_email="nope@email.com",  # doesn't exist
                clearance_id=10354,  # exists
                action="assign",
            ),
            ScheduledAction.ActionConfig(
                assigner_email="person1@email.com",
                assigner_name="John Champion",
                assignee_email="nope@email.com",  # doesn't exist
                clearance_id=10353,  # doesn't exist
                action="assign",
            ),
        ]
    )

    assert result == {
        "succeeded": {
            "person2@email.com": {
                10354: True,
            }
        },
        "failed": {
            "person2@email.com": {10353: "This clearance does not exist in ACS."},
            "nope@email.com": {
                10353: "This assignee does not exist in ACS.",
                10354: "This assignee does not exist in ACS.",
            },
        },
        "already_completed": {},
        "pending": [],
    }

    # verify it logs the assignment errors
    assert (
        "These clearances could not be found and could not be assigned/revoked: 10353"
        in caplog.text
    )
    assert (
        "These people could not be found, and their clearances have not "
        "been assigned/revoked: nope@email.com"
    ) in caplog.text


def test_revoke_invalid_clearances_and_assignees(db, fake_auth, monkeypatch, caplog):
    """It should revoke the valid clearances and assignees and log the ones that don't exist"""
    monkeypatch.setattr(CcureACS, "search", mock_get_clearance_assignments)
    monkeypatch.setattr(acs.personnel, "search", mock_personnel_search)
    monkeypatch.setattr(acs.clearance, "search", lambda *_, **__: clearances)
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_clearances_by_id)
    monkeypatch.setattr(acs.action.personnel, "revoke_clearances", lambda *_, **__: None)
    monkeypatch.setattr(Audit, "add_many", lambda *_, **__: [])

    result = ScheduledAction.process(
        configs=[
            ScheduledAction.ActionConfig(
                assigner_email="person1@email.com",
                assigner_name="John Champion",
                assignee_email="person2@email.com",  # exists
                clearance_id=10354,  # exists
                action="revoke",
            ),
            ScheduledAction.ActionConfig(
                assigner_email="person1@email.com",
                assigner_name="John Champion",
                assignee_email="person2@email.com",  # exists
                clearance_id=10353,  # doesn't exist
                action="revoke",
            ),
            ScheduledAction.ActionConfig(
                assigner_email="person1@email.com",
                assigner_name="John Champion",
                assignee_email="nope@email.com",  # doesn't exist
                clearance_id=10354,  # exists
                action="revoke",
            ),
            ScheduledAction.ActionConfig(
                assigner_email="person1@email.com",
                assigner_name="John Champion",
                assignee_email="nope@email.com",  # doesn't exist
                clearance_id=10353,  # doesn't exist
                action="revoke",
            ),
        ]
    )

    assert result == {
        "succeeded": {
            "person2@email.com": {
                10354: True,
            }
        },
        "failed": {
            "person2@email.com": {10353: "This clearance does not exist in ACS."},
            "nope@email.com": {
                10353: "This assignee does not exist in ACS.",
                10354: "This assignee does not exist in ACS.",
            },
        },
        "already_completed": {},
        "pending": [],
    }

    # verify it logs the assignment errors
    assert (
        "These clearances could not be found and could not be assigned/revoked: 10353"
        in caplog.text
    )
    assert (
        "These people could not be found, and their clearances have not "
        "been assigned/revoked: nope@email.com"
    ) in caplog.text


def test_assign_no_clearances(db, fake_auth, monkeypatch):
    """It should fail if an assignment is attempted with no clearances."""
    monkeypatch.setattr(acs.personnel, "search", mock_personnel_search)
    monkeypatch.setattr(acs.action.personnel, "get_assigned_clearances", lambda *_, **__: [])
    monkeypatch.setattr(acs.action.personnel, "assign_clearances", lambda *_, **__: None)
    monkeypatch.setattr(Personnel, "search_by_email", lambda *_, **__: [personnel])
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_clearances_by_id)
    monkeypatch.setattr(Audit, "add_many", lambda *_, **__: [])

    try:
        result = ScheduledAction.process([])
    except RuntimeError:
        assert False

    assert result == {"succeeded": {}, "failed": {}, "already_completed": {}, "pending": []}


def test_assign_clearance_while_not_in_acs(db, fake_auth, monkeypatch):
    """It should successfully assign a clearance if the assigner is not in ACS."""
    monkeypatch.setattr(acs.personnel, "search", mock_personnel_search)
    monkeypatch.setattr(acs.action.personnel, "get_assigned_clearances", lambda *_, **__: [])
    monkeypatch.setattr(acs.action.personnel, "assign_clearances", lambda *_, **__: None)
    monkeypatch.setattr(Personnel, "search_by_email", lambda *_, **__: [personnel])
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_clearances_by_id)
    monkeypatch.setattr(Audit, "add_many", lambda *_, **__: [])

    try:
        result = ScheduledAction.process(
            configs=[
                ScheduledAction.ActionConfig(
                    assigner_email="staylor8@test.edu",
                    assigner_name="Shawn Taylor",
                    assignee_email="person2@email.com",
                    clearance_id=9497,
                    action="assign",
                )
            ]
        )
    except Exception:
        assert False

    assert result == {
        "succeeded": {"person2@email.com": {9497: True}},
        "failed": {},
        "already_completed": {},
        "pending": [],
    }


def test_assign_with_no_assigner_name(db, fake_auth, monkeypatch):
    """Make sure the email appears as the assigner name in the audit log."""
    monkeypatch.setattr(acs.personnel, "search", mock_personnel_search)
    monkeypatch.setattr(acs.action.personnel, "get_assigned_clearances", lambda *_, **__: [])
    monkeypatch.setattr(acs.action.personnel, "assign_clearances", lambda *_, **__: None)
    monkeypatch.setattr(Personnel, "search_by_email", lambda *_, **__: [personnel])
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_clearances_by_id)

    result = ScheduledAction.process(
        configs=[
            ScheduledAction.ActionConfig(
                assigner_email="service_account@test.edu",
                assigner_name="",
                assignee_email="person2@email.com",
                clearance_id=9497,
                action="assign",
            )
        ]
    )
    assert result == {
        "succeeded": {"person2@email.com": {9497: True}},
        "failed": {},
        "already_completed": {},
        "pending": [],
    }

    log = Audit.get_audit_log()

    assert len(log) == 1
    assigner_name = log[0].assigner_name
    assert assigner_name is not None
    assert assigner_name != ""


def test_revoke_clearance_while_not_in_acs(db, fake_auth, monkeypatch):
    """It should successfully revoke clearances if the assigner is not in ACS."""
    monkeypatch.setattr(acs.personnel, "search", mock_personnel_search)
    monkeypatch.setattr(
        acs.action.personnel, "get_assigned_clearances", mock_get_clearance_assignments
    )
    monkeypatch.setattr(acs.action.personnel, "revoke_clearances", lambda *_, **__: 0)
    monkeypatch.setattr(Personnel, "search_by_email", lambda *_, **__: [personnel])
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_clearances_by_id)
    monkeypatch.setattr(Audit, "add_many", lambda *_, **__: [])

    try:
        result = ScheduledAction.process(
            configs=[
                ScheduledAction.ActionConfig(
                    assigner_email="doesnotexist@university.edu",
                    assigner_name="John Doe",
                    assignee_email="person2@email.com",
                    clearance_id=10354,
                    action="revoke",
                ),
            ]
        )
    except Exception:
        assert False

    assert result == {
        "succeeded": {
            "person2@email.com": {
                10354: True,
            }
        },
        "failed": {},
        "already_completed": {},
        "pending": [],
    }


def test_get_assignment_actions(dbp, fake_auth, monkeypatch):
    """It should get scheduled actions"""
    monkeypatch.setattr(Personnel, "find_one", lambda *_, **__: personnel)
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_clearances_by_id)

    result = ScheduledAction.get(limit=2)
    assert isinstance(result, dict)
    assert len(result) == 2
    actions = result["actions"]
    assert isinstance(actions, list)
    assert len(actions) == 2
    assert result["count"] == 8


def test_get_assignment_actions_filtered(dbp, fake_auth, monkeypatch):
    """It should get future actions according to the given filters"""
    monkeypatch.setattr(Personnel, "find_one", lambda *_, **__: personnel)
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_clearances_by_id)

    now = datetime.now(timezone.utc)
    today = datetime(year=now.year, month=8, day=15, tzinfo=timezone.utc)

    result = ScheduledAction.get(
        assigner_email="person1@email.com",
        assignee_email="person1@email.com",
        from_time=today,
        to_time=today + timedelta(days=15),
        action_type="assign",
    )
    assert isinstance(result, dict)
    assert len(result) == 2
    actions = result["actions"]
    assert isinstance(actions, list)
    assert len(actions) == 1
    assert result["count"] == 1


def test_cancel_future_assignment_action(dbp, fake_auth, monkeypatch):
    """It should cancel a scheduled action"""
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_clearances_by_id)
    now = datetime.now(timezone.utc)
    today = datetime(year=now.year, month=8, day=15, tzinfo=timezone.utc)
    future_actions = ScheduledAction.get(from_time=today, status=["pending"])["actions"]

    assert len(future_actions) == 2

    ScheduledAction.cancel_scheduled_actions(assignment_id_strings=["64625661a3f03b7bcddf2130"])
    future_actions = ScheduledAction.get(from_time=today, status=["pending"])["actions"]
    assert len(future_actions) == 1


def test_process_already_completed_action(dbp, fake_auth, monkeypatch):
    """It should include completed actions in the return value and update documents in mongo"""
    monkeypatch.setattr(
        acs.action.personnel,
        "get_assigned_clearances",
        lambda *_, **__: [{"ClearanceID": 6006}],
    )
    monkeypatch.setattr(
        acs.action.personnel,
        "assign_clearances",
        lambda *_, **__: None,
    )
    monkeypatch.setattr(
        acs.personnel,
        "search",
        lambda *_, **__: [
            {
                "EmailAddress": "assigneremail",
                "ObjectID": 5004,
                "ProperName": "Yon Yonson",
            }
        ],
    )
    monkeypatch.setattr(Personnel, "search_by_email", lambda *_, **__: [personnel])
    monkeypatch.setattr(Clearance, "get_by_ids", mock_get_clearances_by_id)

    scheduled_action_coll = get_clearance_collection("scheduled_action")

    scheduled_assignment_document = scheduled_action_coll.find_one({"clearance_id": 6006})
    assert scheduled_assignment_document is not None
    assert scheduled_assignment_document["status"] == "pending"

    assign_response = ScheduledAction.process(
        [
            ScheduledAction.ActionConfig(
                assigner_email="dummy@email.com",
                assigner_name="Dummy Guy",
                assignee_email="person2@email.com",
                clearance_id=6006,
                action="assign",
                action_time=datetime(
                    datetime.now(timezone.utc).year,
                    1,
                    1,
                    1,
                    1,
                    1,
                    tzinfo=timezone.utc,
                ),
            ),
        ]
    )
    assert assign_response["succeeded"] == {}
    assert assign_response["already_completed"] == {
        "person2@email.com": {6006: "This action has already been done."}
    }

    scheduled_assignment_document = scheduled_action_coll.find_one(
        {
            "assignee_email": "person2@email.com",
            "clearance_id": 6006,
            "action": "assign",
            "action_time": {
                "$lte": datetime(
                    year=datetime.now(timezone.utc).year + 1, month=1, day=1, tzinfo=timezone.utc
                )
                + timedelta(days=10),
            },
        },
    )
    assert scheduled_assignment_document is not None
    assert scheduled_assignment_document["status"] == "already_completed"
