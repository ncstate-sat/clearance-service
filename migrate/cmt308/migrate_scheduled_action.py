import os

from pymongo import MongoClient
from sat.logs import SATLogger

logger = SATLogger(__name__)


class ScheduledActionMigrate:
    coll = MongoClient(os.getenv("CLEARANCE_DB_URL"))["clearance_service"]["scheduled_action"]
    assignee_ids: set[str] = set(coll.distinct("assignee_id", {}))

    @classmethod
    def get_scheduled_action_cids(cls) -> set[str]:
        """Return campus IDs that we'll need to match to email addresses"""
        # we don't need the assigner IDs
        return cls.assignee_ids

    @classmethod
    def migrate(cls, cid_email_map: dict[str, str]):
        """
        1. add 'assignee_email' field and populate it
        2. remove 'assigner_id' and 'assignee_id' fields
        """
        # add assignee email
        unmatched_cids = set()
        updates = 0
        for assignee_cid in cls.assignee_ids:
            if assignee_email := cid_email_map.get(assignee_cid):
                response = cls.coll.update_many(
                    filter={"assignee_id": assignee_cid},
                    update={"$set": {"assignee_email": assignee_email}},
                )
                updates += response.modified_count
            else:
                unmatched_cids.add(assignee_cid)
        logger.info(f"Added assignee emails to {updates} documents.")
        if unmatched_cids:
            logger.info(
                "Could not find email addresses for these campus IDs: " + ", ".join(unmatched_cids)
            )

        # remove assigner_id and assignee_id fields, but only from documents that
        # were actually backfilled with assignee_email -- otherwise documents whose
        # campus ID couldn't be matched to an email would be left with neither field
        response = cls.coll.update_many(
            filter={"assignee_email": {"$exists": True}},
            update={
                "$unset": {
                    "assigner_id": 1,
                    "assignee_id": 1,
                },
            },
        )
        logger.info(f"Removed fields from {response.modified_count} documents.")
