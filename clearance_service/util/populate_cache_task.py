from aiocache import Cache
from sat.logs import SATLogger

from clearance_service.models.door import Door

logger = SATLogger(__name__)
cache = Cache()  # defaults to in-memory. we can do redis if we want


async def populate_door_names_cache():
    """
    Query acslib to get the ID and name of every door, then hold the results in memory.
    The /assignments/{email}?get_doors=true endpoint will load door names from this cache.
    Runs when the service starts, then once daily.
    """
    door_names = Door.get_all_names()
    await cache.set("door_names", door_names)
    if await cache.get("door_names") == door_names:
        logger.info("Loaded door names into the door cache.")
    else:
        logger.error("Not able to load door names into the server cache.")


async def get_cached_door_names() -> dict:
    """Return the cached door names keyed by door ID, or an empty dict if the cache is empty."""
    return await cache.get("door_names") or {}
