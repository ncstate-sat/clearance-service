from datetime import datetime, timezone

from bson import ObjectId

from clearance_service.models.space_schedule import SpaceSchedule


def test_create_space_schedule(dbp, fake_auth):
    """It should add a space schedule to the db"""
    original_schedules = list(dbp.space_schedule.find({}))

    assert len(original_schedules) == 3

    new_schedule = SpaceSchedule("68a36894e6decd139abbe089", datetime.now(), "unlock")
    create_result = new_schedule.create()
    assert create_result.acknowledged is True
    assert isinstance(create_result.inserted_id, ObjectId)

    all_schedules = list(dbp.space_schedule.find({}))
    assert len(all_schedules) == 4

    new_mongo_schedule = dbp.space_schedule.find_one({"_id": create_result.inserted_id})

    assert sorted(new_mongo_schedule) == [
        "_id",
        "action_time",
        "action_type",
        "created_by",
        "created_on",
        "modified_on",
        "series_name",
        "space_id",
    ]
    assert new_mongo_schedule["created_on"] == new_mongo_schedule["modified_on"]
    assert new_mongo_schedule["series_name"] is None


def test_search_space_schedules(dbp, fake_auth):
    """It should search space schedules in mongo"""
    assert len(list(dbp.space_schedule.find({}))) == 3
    assert len(SpaceSchedule.search({}, skip=0, limit=10)) == 3
    assert len(SpaceSchedule.search({"series_name": {"$regex": "test_series1"}}, 0, 10)) == 2
    assert len(SpaceSchedule.search({"series_name": {"$regex": "test_series1"}}, 1, 10)) == 1
    assert len(SpaceSchedule.search({"series_name": {"$regex": "test_series1"}}, 0, 1)) == 1
    assert len(SpaceSchedule.search({"series_name": {"$regex": "test_series2"}}, 0, 10)) == 1


def test_update_space_schedule(dbp, fake_auth):
    """It should update the space or action time of a space schedule in mongo"""
    schedule = dbp.space_schedule.find_one({"_id": ObjectId("68d45dd062efa1978c6b854b")})
    assert isinstance(schedule["action_time"], datetime)
    original_action_time = schedule["action_time"]
    assert schedule["space_id"] == ObjectId("68a36894e6decd139abbe088")

    update_response = SpaceSchedule.update(
        schedule_id=str(schedule["_id"]),
        space_id="68a36894e6decd139abbe000",
        action_time=datetime.now(timezone.utc),
        user_email=None,
    )
    assert update_response.matched_count == 1
    updated_schedule = dbp.space_schedule.find_one({"_id": schedule["_id"]})
    assert updated_schedule["action_time"] > original_action_time
    assert updated_schedule["space_id"] == ObjectId("68a36894e6decd139abbe000")


def test_delete_space_schedule(dbp, fake_auth):
    """It should delete a space schedule document from the db"""
    schedule = dbp.space_schedule.find_one({"_id": ObjectId("68d45dd062efa1978c6b854b")})
    assert schedule is not None

    delete_response = SpaceSchedule.delete(str(schedule["_id"]), None)
    assert delete_response.deleted_count == 1

    new_search_results = dbp.space.find_one({"_id": ObjectId("68d45dd062efa1978c6b854b")})
    assert new_search_results is None
