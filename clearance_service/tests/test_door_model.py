from clearance_service.models.door import Door


def test_door_hash_eq():
    door1 = Door(3001, "door1")
    door2 = Door(3002, "door2")
    door_dupe = Door(3001, "dupe door")

    assert door1 == door_dupe
    assert door1 != door2
    try:
        door_set = {door1, door2, door_dupe}
    except Exception:
        assert False
    assert len(door_set) == 2
