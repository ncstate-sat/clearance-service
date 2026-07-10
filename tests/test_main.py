import os
from unittest import mock

from main import startup_db_client


@mock.patch.dict(os.environ, {}, clear=True)
def test_service_scheduler_runs(caplog):
    startup_db_client()
    assert "Scheduler started" in caplog.text


@mock.patch.dict(os.environ, {"DEVELOPMENT": "True"}, clear=True)
def test_service_scheduler_does_not_run(caplog):
    startup_db_client()
    assert "DEVELOPMENT mode, not starting scheduler" in caplog.text
