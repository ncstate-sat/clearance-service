from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pymongo.results import InsertOneResult

from clearance_service.util.db_connect import get_clearance_collection


class SpaceSchedule:
    space_schedule_coll = get_clearance_collection("space_schedule")

    def __init__(
        self,
        space_id: str,
        action_time: datetime,
        action_type: str,
        series_name: Optional[str] = None,
        created_by: str = "",  # email
        created_on: Optional[datetime] = None,
        modified_on: Optional[datetime] = None,
    ):
        self.space_id = space_id
        self.created_by = created_by
        self.created_on = created_on
        self.modified_on = modified_on
        self.action_time = action_time
        self.action_type = action_type
        self.series_name = series_name

    def create(self) -> InsertOneResult:
        now = datetime.now(timezone.utc)
        return self.space_schedule_coll.insert_one(
            {
                "space_id": ObjectId(self.space_id),
                "action_time": self.action_time,
                "action_type": self.action_type,
                "series_name": self.series_name,
                "created_by": self.created_by,
                "created_on": now,
                "modified_on": now,
            }
        )

    @classmethod
    def search(cls, criteria: dict, skip: int, limit: int) -> list:
        return list(cls.space_schedule_coll.find(criteria).skip(skip).limit(limit))

    @classmethod
    def update(
        cls,
        schedule_id: str,
        space_id: Optional[str],
        action_time: Optional[datetime],
        user_email: Optional[str],
    ):
        return cls.space_schedule_coll.update_one(
            {"_id": ObjectId(schedule_id)} | ({"created_by": user_email} if user_email else {}),
            {
                "$set": {"modified_on": datetime.now(timezone.utc)}
                | ({"space_id": ObjectId(space_id)} if space_id is not None else {})
                | ({"action_time": action_time} if action_time is not None else {})
            },
        )

    @classmethod
    def delete(cls, schedule_id: str, user_email: Optional[str]):
        return cls.space_schedule_coll.delete_one(
            {"_id": ObjectId(schedule_id)} | ({"created_by": user_email} if user_email else {})
        )
