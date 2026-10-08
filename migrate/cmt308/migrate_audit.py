import os

from pymongo import MongoClient
from sat.logs import SATLogger


logger = SATLogger(__name__)


class AuditMigrate:
    coll = MongoClient(os.getenv("CLEARANCE_DB_URL"))["clearance_service"]["audit"]
    assigners: set[str] = set(filter(None, coll.distinct("assigner_id", {})))
    assignees: set[str] = set(filter(None, coll.distinct("assignee_id", {})))

    @classmethod
    def get_audit_cids(cls) -> set[str]:
        return cls.assigners | cls.assignees

    @classmethod
    def migrate(cls, cid_email_map: dict[str, str]):
        """
        1. change 'assigner' to 'assigner_name'
        2. change 'assignee' to 'assignee_name'
        3. add 'assigner_email' and 'assignee_email' fields and populate them
        4. remove 'assigner_id' and 'assignee_id' fields
        """
        # rename fields
        response = cls.coll.update_many(
            filter={},
            update={"$rename": {
                "assigner": "assigner_name",
                "assignee": "assignee_name",
            }},
        )
        logger.info(f"Renamed fields on {response.modified_count} documents.")

        # add assigner email
        unmatched_cids = set()
        updates = 0
        for assigner_cid in cls.assigners:
            if assigner_email := cid_email_map.get(assigner_cid):
                response = cls.coll.update_many(
                    filter={"assigner_id": assigner_cid},
                    update={"$set": {"assigner_email": assigner_email}},
                )
                updates += response.modified_count
            else:
                unmatched_cids.add(assigner_cid)
        logger.info(f"Added assigner emails to {updates} documents.")
        if unmatched_cids:
            logger.info(
                "Could not find email addresses for these assigner campus IDs: "
                + ", ".join(unmatched_cids)
            )

        # add assignee email
        unmatched_cids = set()
        updates = 0
        for assignee_cid in cls.assignees:
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
                "Could not find email addresses for these assignee campus IDs: "
                + ", ".join(unmatched_cids)
            )

        # remove assigner_id and assignee_id fields
        response = cls.coll.update_many(
            filter={},
            update={
                "$unset": {
                    "assigner_id": 1,
                    "assignee_id": 1,
                },
            },
        )
        logger.info(f"Removed campus ID fields from {response.modified_count} documents.")
