"""Model for clearance assignment audit"""
from datetime import datetime, timezone, date
from typing import Optional

from pydantic import BaseModel

from clearance_service.models import acs, filters
from clearance_service.util.db_connect import get_clearance_collection

from acslib.base.search import BooleanOperators


class Audit:
    """Model for clearance assignment audit"""

    collection = get_clearance_collection("audit")

    class AuditRecord(BaseModel):
        """Model for initializing new Audit objects"""

        assigner_name: str
        assignee_name: str
        action: str
        timestamp: datetime

    def __init__(self, audit_data: AuditRecord):
        self.assigner_name = audit_data.assigner_name
        self.assignee_name = audit_data.assignee_name
        self.action = audit_data.action
        self.timestamp = audit_data.timestamp.isoformat() + "Z"

    class NewAuditData(BaseModel):
        """audit_config model for adding audit records"""

        assigner_email: str
        assigner_name: str
        assignee_email: str
        clearance_id: int
        clearance_name: str
        message_base: str

    @classmethod
    def add_many(cls, audit_configs: list[NewAuditData]) -> list[str]:
        """Add multiple audit entries"""
        if not audit_configs:
            return []

        now = datetime.now(timezone.utc)
        people_emails = set()
        for config in audit_configs:
            people_emails.add(config.assigner_email)
            people_emails.add(config.assignee_email)

        search_filter = filters.PersonnelFilter(
            lookups={"EmailAddress": filters.NFUZZ},
            outer_bool=BooleanOperators.OR,
            display_properties=[],
        )
        people_records = acs.personnel.search(list(people_emails), search_filter)
        names_by_email = {
            person["EmailAddress"]: person["ProperName"]
            for person in people_records
        }
        result = cls.collection.insert_many(
            [
                {
                    "assigner_name": names_by_email.get(
                        config.assigner_email,
                        config.assigner_name
                        if config.assigner_name is not None
                        else config.assigner_email,
                    ),
                    "assigner_email": config.assigner_email,
                    "assignee_name": names_by_email.get(config.assignee_email, ""),
                    "assignee_email": config.assignee_email,
                    "action": config.clearance_name + config.message_base,
                    "clearance_id": config.clearance_id,
                    "clearance_name": config.clearance_name,
                    "timestamp": now,
                }
                for config in audit_configs
            ]
        )
        return result.inserted_ids

    @classmethod
    def get_audit_log(
        cls,
        assignee_email: Optional[str] = None,
        assigner_email: Optional[str] = None,
        clearance_id: Optional[int] = None,
        clearance_name: Optional[str] = None,
        from_time: Optional[date] = None,
        to_time: Optional[date] = None,
        skip: int = 0,
        limit: int = 50,
        action: Optional[str] = None,
    ) -> list["Audit"]:
        """
        Get records from the audit collection with optional filters

        Parameters:
            assignee_email: the email address of the assignee
            assigner_email: the email address of the assigner
            clearance_id: the clearance's ID
            clearance_name: the clearance's title
            from_time: the minimum timestamp for returned audits
            to_time: the maximum timestamp for returned audits
            skip: the number of documents to skip
            limit: maximum number of results to return
            action: a regex to search audit messages

        Returns: A list of Audit objects
        """
        match = {}
        if assignee_email is not None:
            match["assignee_email"] = assignee_email
        if assigner_email is not None:
            match["assigner_email"] = assigner_email
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
        if action is not None:
            match["action"] = {"$regex": action, "$options": "i"}  # case insensitive

        audit_results = cls.collection.aggregate(
            [
                {"$match": match},
                {"$project": {
                    "_id": 0,
                    "assigner_name": 1,
                    "assignee_name": 1,
                    "action": 1,
                    "timestamp": 1,
                }},
                {"$sort": {"timestamp": -1}},
                {"$skip": skip},
                {"$limit": limit},
            ]
        )
        return [Audit(Audit.AuditRecord(**audit_record)) for audit_record in audit_results]

    @classmethod
    def get_monthly_report(cls) -> list[dict]:
        """
        Get assignments and revocations by user by month, for the last twelve full months
        """
        now = datetime.now(timezone.utc)
        start_time = datetime(
            year=now.year - 1,
            month=now.month,
            day=1,
        )
        stop_time = datetime(
            year=now.year,
            month=now.month,
            day=1,
        )

        response = cls.collection.aggregate(
            [
                {
                    "$match": {
                        "timestamp": {
                            "$gt": start_time,
                            "$lt": stop_time,
                        }
                    }
                },
                {
                    "$group": {
                        "_id": {
                            "assigner": "$assigner",
                            "assigner_email": "$assigner_email",
                            "month": {"$month": "$timestamp"},
                            "year": {"$year": "$timestamp"},
                        },
                        "assignments": {"$sum": 1},
                    }
                },
                {
                    "$project": {
                        "data": {
                            "month": "$_id.month",
                            "year": "$_id.year",
                            "assignments": "$assignments",
                        },
                    }
                },
                {"$sort": {"data.year": 1, "data.month": 1}},
                {
                    "$group": {
                        "_id": {
                            "assigner": "$_id.assigner",
                            "assigner_email": "$_id.assigner_email",
                        },
                        "monthly_assignments": {"$push": "$data"},
                    }
                },
                {"$sort": {"_id.assigner_name": 1}},
            ]
        )
        return list(response)
