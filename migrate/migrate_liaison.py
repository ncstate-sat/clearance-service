import os

from pymongo import MongoClient
from sat.logs import SATLogger


logger = SATLogger(__name__)


class LiaisonMigrate:
    coll = MongoClient(os.getenv("CLEARANCE_DB_URL"))["clearance_service"]["liaison"]

    @classmethod
    def migrate(cls):
        """
        1. remove campus_id field
        """
        response = cls.coll.update_many(
            filter={},
            update={"$unset": {"campus_id": 1}},
        )
        logger.info(f"Removed campus ID field from {response.modified_count} documents.")
