import pytest

from clearance_service.models import acs
from clearance_service.util import populate_cache_task
from clearance_service.util.handle_requests import RequestException
from clearance_service.util.populate_cache_task import (
    get_cached_door_names,
    populate_door_names_cache,
)

pytestmark = [pytest.mark.anyio, pytest.mark.usefixtures("clear_cache")]

CCURE_DOORS = [
    {
        "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
        "ObjectID": 3000,
        "Name": "VRB-B-B103C-Test Door 1234",
        "*PK": ["ObjectID"],
    },
    {
        "ClassType": "SoftwareHouse.NextGen.Common.SecurityObjects.iStarDoor",
        "ObjectID": 3001,
        "Name": "VRB-B-B103C-Test Door 5678",
        "*PK": ["ObjectID"],
    },
]
DOOR_NAMES = {3000: "VRB-B-B103C-Test Door 1234", 3001: "VRB-B-B103C-Test Door 5678"}


@pytest.fixture
def mock_ccure(mocker):
    """Replace the CCURE door search with canned results."""
    return mocker.patch.object(acs.ccure_object, "search", return_value=CCURE_DOORS)


async def test_stores_door_names_in_cache(mock_ccure, clear_cache):
    await populate_door_names_cache()

    assert await clear_cache.get("door_names") == DOOR_NAMES


async def test_queries_every_door(mock_ccure):
    await populate_door_names_cache()

    mock_ccure.assert_called_once()
    assert mock_ccure.call_args.kwargs["terms"] == []


async def test_empty_ccure_response_caches_empty_dict(mock_ccure, clear_cache):
    mock_ccure.return_value = []

    await populate_door_names_cache()

    assert await clear_cache.get("door_names") == {}


async def test_replaces_previous_cache_contents(mock_ccure, clear_cache):
    await clear_cache.set("door_names", {1: "stale door"})

    await populate_door_names_cache()

    assert await clear_cache.get("door_names") == DOOR_NAMES


async def test_logs_success(mock_ccure, mocker):
    logger = mocker.patch.object(populate_cache_task, "logger")

    await populate_door_names_cache()

    logger.info.assert_called_once_with("Loaded door names into the door cache.")
    logger.error.assert_not_called()


async def test_logs_error_when_cache_does_not_hold_door_names(mock_ccure, mocker):
    logger = mocker.patch.object(populate_cache_task, "logger")
    mocker.patch.object(populate_cache_task.cache, "get", return_value=None)

    await populate_door_names_cache()

    logger.error.assert_called_once_with("Not able to load door names into the server cache.")
    logger.info.assert_not_called()


async def test_ccure_errors_propagate_and_keep_existing_cache(mock_ccure, clear_cache):
    await clear_cache.set("door_names", DOOR_NAMES)
    mock_ccure.side_effect = RequestException(503, "CCURE unavailable")

    with pytest.raises(RequestException):
        await populate_door_names_cache()

    assert await clear_cache.get("door_names") == DOOR_NAMES


async def test_get_cached_door_names_returns_cached_names(clear_cache):
    await clear_cache.set("door_names", DOOR_NAMES)

    assert await get_cached_door_names() == DOOR_NAMES


async def test_get_cached_door_names_returns_empty_dict_when_cache_is_empty():
    assert await get_cached_door_names() == {}
