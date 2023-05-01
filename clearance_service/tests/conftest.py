import os

import pytest
from auth_checker import AuthChecker
from pymongo import MongoClient

mongo_client = MongoClient(os.getenv("TEST_DB_URL"))


def setup_db():
    """Todo: Sanely handle the case where the server isn't running
    Currently mongo or PyMongo will happily return a MongoClient even
    if the server is offline. When an operation is attempted, it will
    hang without raising an exception.
    """


def tear_down_db():
    db = mongo_client.clearance_service
    for collection in db.list_collection_names():
        db.drop_collection(collection)


@pytest.fixture(autouse=True)
def before_and_after_test():
    setup_db()
    yield
    tear_down_db()


@pytest.fixture
def db():
    return mongo_client.clearance_service


@pytest.fixture
def fake_auth(monkeypatch):
    monkeypatch.setattr(AuthChecker, "check_authorization", lambda *_, **__: None)
