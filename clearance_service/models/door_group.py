from acslib.base.search import BooleanOperators
from acslib.ccure.types import ObjectType

from clearance_service.models import acs, filters
from clearance_service.models.door import Door


class DoorGroup:
    def __init__(self, acs_id: int, name: str):
        self.id = acs_id
        self.name = name
        self.type = "door group"

    def populate_doors(self):
        group_members = acs.group_member.search(
            [self.id],
            filters.GroupMemberFilter(lookups={"GroupID": filters.NFUZZ}),
            page_size=10000,
        )
        door_ids = [item["TargetObjectID"] for item in group_members]
        door_filter = filters.ClearanceItemFilter(
            lookups={"ObjectID": filters.NFUZZ},
            outer_bool=BooleanOperators.OR,
            display_properties=["ObjectID", "Name"],
        )
        acs_doors = acs.ccure_object.search(
            object_type=ObjectType.DOOR.complete,
            terms=door_ids,
            search_filter=door_filter,
        )
        self.doors = [Door(door["ObjectID"], door["Name"]) for door in acs_doors]
