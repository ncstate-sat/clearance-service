from pymongo import MongoClient
import pytest

mongo_client = MongoClient('mongodb://localhost:27017')


@pytest.fixture(scope="function", autouse=True)
def wipe_data():
    # Clean up the database after each test
    yield
    mongo_client.drop_database('clearance_service')
    mongo_client.drop_database('db')
