"""Tests for the Clearance Assignment model"""


from clearance_service.models import acs
from clearance_service.models.clearance import Clearance
from clearance_service.models.personnel import Personnel


def mock_clearance_item_search(*_, **__):
    return [
        {
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.ClearanceItem",
            "DoorGroupID": None,
            "DoorID": 3000,
            "ObjectID": 5008,
            # etc.
        },
        {
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.ClearanceItem",
            "DoorGroupID": 4000,
            "DoorID": None,
            "ObjectID": 5009,
        },
    ]


def mock_ccure_object_search(*_, **__):
    return [
        {
            "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
            "Name": "testdoor3000",
            "ObjectID": 3000,
            # etc.
        },
    ]


def mock_ccure_group_search(*_, **__):
    return [
        {
            "ClassType": "SoftwareHouse.CrossFire.Common.Objects.Group",
            "GroupType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
            "Name": "testdoorgroup4000",
            "ObjectID": 4000,
            # etc.
        },
    ]


def mock_ccure_group_member_search(*_, **__):
    return [
        {
            "ClassType": "SoftwareHouse.CrossFire.Common.Objects.GroupMember",
            "GroupID": 4000,
            "GroupType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
            "ObjectID": 5004,
            "TargetObjectID": 3000,
            # etc.
        },
    ]


def test_get_doors(db, fake_auth, monkeypatch):
    """It should get doors and door groups from acs"""
    monkeypatch.setattr(
        acs.clearance_item,
        "search",
        mock_clearance_item_search,
    )
    monkeypatch.setattr(
        acs.ccure_object,
        "search",
        mock_ccure_object_search,
    )
    monkeypatch.setattr(
        acs.group,
        "search",
        mock_ccure_group_search,
    )
    monkeypatch.setattr(
        acs.group_member,
        "search",
        mock_ccure_group_member_search,
    )
    monkeypatch.setattr(Clearance, "get_allowed", lambda _: [Clearance(1000, "fake_clearance")])

    all_doors_and_groups = Personnel.get_doors("fake@email.no")
    assert isinstance(all_doors_and_groups, list)
    assert all_doors_and_groups[0].type == "door"
    assert all_doors_and_groups[-1].type == "door group"
    door = all_doors_and_groups[0]
    door_group = all_doors_and_groups[-1]
    assert door.id == 3000
    assert door.name == "testdoor3000"
    assert door_group.id == 4000
    assert door_group.name == "testdoorgroup4000"
    assert isinstance(door_group.doors, list)


def test_get_doors_ungrouped(db, fake_auth, monkeypatch):
    """It should get a flat list of doors from acs"""
    monkeypatch.setattr(
        acs.clearance_item,
        "search",
        mock_clearance_item_search,
    )
    monkeypatch.setattr(
        acs.ccure_object,
        "search",
        mock_ccure_object_search,
    )
    monkeypatch.setattr(
        acs.group,
        "search",
        mock_ccure_group_search,
    )
    monkeypatch.setattr(
        acs.group_member,
        "search",
        mock_ccure_group_member_search,
    )
    monkeypatch.setattr(Clearance, "get_allowed", lambda _: [Clearance(1000, "fake_clearance")])

    all_doors = Personnel.get_doors_ungrouped("fake@email.ok")
    assert isinstance(all_doors, set)
    assert all(item.type == "door" for item in all_doors)
    assert len(all_doors) == 1
