from typing import Optional

from acslib.base.search import BooleanOperators
from acslib.ccure.types import ObjectType

from clearance_service.models import acs, filters


class Door:
    def __init__(self, acs_id: int, name: str):
        self.id = acs_id
        self.name = name
        self.type = "door"

    def __eq__(self, other):
        return self.id == other.id

    def __hash__(self):
        return hash(self.id)

    @staticmethod
    def get_all_names() -> dict[int, Optional[str]]:
        """Get the name of every door in CCure, keyed by door ID."""
        return Door._search_names(terms=[], timeout=180)

    @staticmethod
    def get_names_by_ids(door_ids: list[int]) -> dict[int, Optional[str]]:
        """Get the names of the given doors, keyed by door ID."""
        if not door_ids:
            return {}
        return Door._search_names(terms=door_ids, timeout=35)

    @staticmethod
    def _search_names(terms: list[int], timeout: int) -> dict[int, Optional[str]]:
        """Search CCure doors by ID; empty terms match every door."""
        door_search_filter = filters.ClearanceItemFilter(
            lookups={"ObjectID": filters.NFUZZ},
            outer_bool=BooleanOperators.OR,
            display_properties=["ObjectID", "Name"],
        )
        acs_doors = acs.ccure_object.search(
            object_type=ObjectType.DOOR.complete,
            search_filter=door_search_filter,
            terms=terms,
            timeout=timeout,
            page_size=99999,
        )
        return {door["ObjectID"]: door["Name"] for door in acs_doors}
