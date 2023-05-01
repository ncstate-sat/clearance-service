"""Model for clearance assignment audit"""

import datetime
from typing import Optional

from pydantic import BaseModel

from clearance_service.models.clearance import Clearance
from clearance_service.util.db_connect import get_clearance_collection


class Audit:
    """Model for clearance assignment audit"""

    collection = get_clearance_collection("audit")

    def __init__(
        self, assigner_id, assignee_id, timestamp, message, clearance_id, clearance_name=None
    ):
        self.assigner_id = assigner_id
        self.assignee_id = assignee_id
        self.timestamp = timestamp.isoformat() + "Z"
        self.message = message
        self.clearance = Clearance(clearance_id, name=clearance_name)

    class AuditData(BaseModel):
        """Model for audit data"""

        assigner_id: str
        assignee_id: str
        clearance_id: str
        timestamp: datetime.datetime
        message: str

    @classmethod
    def add_one(cls, audit_config: AuditData):
        """Add a new audit entry"""
        result = cls.collection.insert_one(audit_config)
        return result.inserted_id

    @classmethod
    def add_many(cls, audit_configs: list[AuditData]):
        """Add multiple audit entries"""
        if audit_configs:
            result = cls.collection.insert_many(audit_configs)
            return result.inserted_ids
        return []

    @classmethod
    def get_audit_log(
        cls,
        assignee_id: Optional[str],
        assigner_id: Optional[str],
        clearance_id: Optional[str],
        clearance_name: str,
        from_time: Optional[datetime.date],
        to_time: Optional[datetime.date],
        skip: int,
        limit: int,
        message: Optional[str] = None,
    ) -> list["Audit"]:
        """
        Get records from the audit collection with optional filters

        Parameters:
            assignee_id: the campus ID of the assignee
            assigner_id: the campus ID of the assigner
            clearance_id: the clearance's GUID
            clearance_name: the clearance's title
            from_time: the minimum timestamp for returned audits
            to_time: the maximum timestamp for returned audits
            message: a regex to search audit messages
            skip: the number of documents to skip
            limit: maximum number of results to return

        Returns: A list of Audit objects
        """
        match = {}
        if assignee_id is not None:
            match["assignee_id"] = assignee_id
        if assigner_id is not None:
            match["assigner_id"] = assigner_id
        if from_time or to_time:
            match["timestamp"] = {}
            if from_time is not None:
                match["timestamp"]["$gte"] = from_time
            if to_time is not None:
                match["timestamp"]["$lt"] = to_time
        if clearance_id is not None:
            match["clearance_id"] = clearance_id
        if clearance_name is not None:
            match["clearance_name"] = {
                "$regex": clearance_name,
                "$options": "i",  # case insensitive
            }
        if message is not None:
            match["message"] = {"$regex": message, "$options": "i"}  # case insensitive

        audit_results: list[dict] = cls.collection.aggregate(
            [
                {"$match": match},
                {"$project": {"_id": 0}},
                {"$sort": {"timestamp": -1}},
                {"$skip": skip},
                {"$limit": limit},
            ]
        )

        return [Audit(**audit_record) for audit_record in audit_results]
