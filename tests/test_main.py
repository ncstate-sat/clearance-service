import asyncio
import os
from unittest import mock

from main import startup_db_client


@mock.patch.dict(os.environ, {}, clear=True)
@mock.patch("main.populate_door_names_cache")
def test_service_scheduler_runs(_, caplog):
    asyncio.run(startup_db_client())
    assert "Scheduler started" in caplog.text


@mock.patch.dict(os.environ, {"DEVELOPMENT": "True"}, clear=True)
@mock.patch("main.populate_door_names_cache")
def test_service_scheduler_does_not_run(_, caplog):
    asyncio.run(startup_db_client())
    assert "DEVELOPMENT mode, not starting scheduler" in caplog.text


@mock.patch.dict(os.environ, {"DEVELOPMENT": "True"}, clear=True)
@mock.patch("main.populate_door_names_cache")
def test_startup_loads_door_names_cache(populate_door_names_cache):
    asyncio.run(startup_db_client())
    populate_door_names_cache.assert_awaited_once_with()
