from bson import ObjectId

from clearance_service.models.space import Space


def test_create_space(dbp, fake_auth):
    """It should add a space to the db"""
    original_spaces = list(dbp.space.find({}))

    assert len(original_spaces) == 4

    new_space = Space("newspace", [1, 2, 3])
    create_result = new_space.create()
    assert create_result.acknowledged is True
    assert isinstance(create_result.inserted_id, ObjectId)

    all_spaces = list(dbp.space.find({}))
    assert len(all_spaces) == 5

    new_mongo_space = dbp.space.find_one({"_id": create_result.inserted_id})

    assert sorted(new_mongo_space) == [
        "_id",
        "created_by",
        "created_on",
        "door_ids",
        "modified_on",
        "name",
    ]
    assert new_mongo_space["created_on"] == new_mongo_space["modified_on"]
    assert new_mongo_space["name"] == "newspace"
    assert new_mongo_space["door_ids"] == [1, 2, 3]


def test_search_space(dbp, fake_auth):
    """It should search spaces in mongo"""
    assert len(list(dbp.space.find({}))) == 4
    assert len(Space.search({}, skip=0, limit=10)) == 4
    assert len(Space.search({"name": {"$regex": "testspace"}}, 0, 10)) == 3
    assert len(Space.search({"name": {"$regex": "testspace"}}, 2, 10)) == 1
    assert len(Space.search({"name": {"$regex": "testspace"}}, 0, 1)) == 1


def test_update_space(dbp, fake_auth):
    """It should update name or door_ids property of a mongo space document"""
    other_space = dbp.space.find_one({"name": "other"})
    assert other_space["name"] == "other"

    update_response = Space.update(
        other_space["_id"],
        new_name="other_renamed",
        new_door_ids=None,
        user_email=None,
    )
    assert update_response.matched_count == 1
    other_space_updated_name = dbp.space.find_one({"_id": other_space["_id"]})
    assert other_space_updated_name["name"] == "other_renamed"
    assert other_space_updated_name["door_ids"] == [9999, 8888]  # unchanged

    update_response = Space.update(
        other_space["_id"],
        new_name=None,
        new_door_ids=[9999, 8888, 7777],
        user_email=None,
    )
    assert update_response.matched_count == 1
    other_space_updated_doors = dbp.space.find_one({"_id": other_space["_id"]})
    assert other_space_updated_doors["name"] == "other_renamed"  # unchanged
    assert other_space_updated_doors["door_ids"] == [9999, 8888, 7777]


def test_delete_space(dbp, fake_auth):
    """It should delete a space document from the db"""
    other_space = dbp.space.find_one({"name": "other"})
    assert other_space is not None

    delete_response = Space.delete(str(other_space["_id"]), None)
    assert delete_response.deleted_count == 1

    new_other_space = dbp.space.find_one({"name": "other"})
    assert new_other_space is None
