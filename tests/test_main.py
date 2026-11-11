import asyncio
import os
from unittest import mock

from acslib.base import ACSRequestException
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


@mock.patch.dict(os.environ, {"DEVELOPMENT": "True"}, clear=True)
@mock.patch(
    "clearance_service.util.populate_cache_task.Door.get_all_names",
    side_effect=ACSRequestException(503, "CCURE unavailable"),
)
def test_startup_succeeds_when_ccure_is_unavailable(_, caplog):
    asyncio.run(startup_db_client())

    assert "DEVELOPMENT mode, not starting scheduler" in caplog.text
    assert "Not able to fetch door names from CCure" in caplog.text
