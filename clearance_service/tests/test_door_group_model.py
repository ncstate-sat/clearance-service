from clearance_service.models import acs
from clearance_service.models.door import Door
from clearance_service.models.door_group import DoorGroup


def test_get_doors_attribute(monkeypatch):
    monkeypatch.setattr(
        acs.group_member,
        "search",
        lambda *_, **__: [
            {
                "ClassType": "SoftwareHouse.CrossFire.Common.Objects.GroupMember",
                "GroupID": 4000,
                "GroupType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
                "ObjectID": 5004,
                "TargetObjectID": 3000,
                # etc.
            },
            {
                "ClassType": "SoftwareHouse.CrossFire.Common.Objects.GroupMember",
                "GroupID": 4000,
                "GroupType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
                "ObjectID": 5005,
                "TargetObjectID": 3001,
            },
        ],
    )
    monkeypatch.setattr(
        acs.ccure_object,
        "search",
        lambda *_, **__: [
            {
                "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
                "Name": "testdoor3000",
                "ObjectID": 3000,
                # etc.
            },
            {
                "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
                "Name": "testdoor3001",
                "ObjectID": 3001,
            },
        ],
    )

    door_group1 = DoorGroup(4001, "door_group1")
    assert door_group1.id == 4001
    assert door_group1.name == "door_group1"
    assert door_group1.type == "door group"

    door_group2 = DoorGroup(4002, "door_group2")
    door_group2.populate_doors()
    assert door_group2.doors == [Door(3000, "testdoor3000"), Door(3001, "testdoor3001")]
