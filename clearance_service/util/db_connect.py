"""Manage the service's connection to the MongoDB database"""

import os

from pymongo import MongoClient
from sat.logs import SATLogger

logger = SATLogger(__name__)


def get_clearance_collection(collection_name):
    """Return a collection from the clearance database."""
    client_url = os.getenv("CLEARANCE_DB_URL")
    if not client_url:
        logger.error("No 'CLEARANCE_DB_URL' variable found")
        raise ValueError('No "CLEARANCE_DB_URL" variable found')
    client = MongoClient(client_url)
    db = client["clearance_service"]
    return db[collection_name]
