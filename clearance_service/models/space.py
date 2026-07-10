from datetime import datetime, timezone
from typing import Optional

from bson import ObjectId
from pymongo.results import InsertOneResult

from clearance_service.util.db_connect import get_clearance_collection


class Space:
    space_coll = get_clearance_collection("space")

    def __init__(
        self,
        name: str,
        door_ids: list[int],
        created_on: Optional[datetime] = None,
        modified_on: Optional[datetime] = None,
        created_by: Optional[str] = None,  # email
        _id: Optional[ObjectId] = None,
    ):
        self.id = _id
        self.name = name
        self.created_on = created_on
        self.modified_on = modified_on
        self.created_by = created_by
        self.door_ids = door_ids

    def create(self) -> InsertOneResult:
        now = datetime.now(timezone.utc)
        return self.space_coll.insert_one(
            {
                "name": self.name,
                "door_ids": self.door_ids,
                "created_on": now,
                "modified_on": now,
                "created_by": self.created_by,
            }
        )

    @classmethod
    def search(cls, criteria: dict, skip: int, limit: int) -> list:
        return list(cls.space_coll.find(criteria).skip(skip).limit(limit))

    @classmethod
    def update(
        cls,
        space_id: str,
        new_name: Optional[str],
        new_door_ids: Optional[list[int]],
        user_email: Optional[str],
    ):
        return cls.space_coll.update_one(
            {"_id": ObjectId(space_id)} | ({"created_by": user_email} if user_email else {}),
            {
                "$set": {"modified_on": datetime.now(timezone.utc)}
                | ({"name": new_name} if new_name is not None else {})
                | ({"door_ids": new_door_ids} if new_door_ids is not None else {})
            },
        )

    @classmethod
    def delete(cls, space_id: str, user_email: Optional[str]):
        return cls.space_coll.delete_one(
            {"_id": ObjectId(space_id)} | ({"created_by": user_email} if user_email else {})
        )
