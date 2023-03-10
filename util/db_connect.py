"""Manage the service's connection to the MongoDB datbase"""

import os
from pymongo import MongoClient


def get_clearance_collection(collection_name):
    """Return a collection from the clearance database."""
    client_url = os.getenv("CLEARANCE_DB_URL") or "mongodb://localhost:27017"
    if not client_url:
        raise ValueError('No "CLEARANCE_DB_URL" variable found')
    client = MongoClient(client_url)
    db = client["clearance_service"]
    return db[collection_name]
