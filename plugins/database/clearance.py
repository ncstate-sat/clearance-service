"""
Database model to interact with a MongoDB database for the Clearance model.
"""

from util.db_connect import get_clearance_collection


class ClearanceDB:
    """
    Plugin model to interface with MongoDB.
    """

    @staticmethod
    def get_clearance_permissions_by_campus_id(campus_id: str) -> list[dict]:
        """
        Gets a list of clearance permissions given a campus id.

        Parameters:
            campus_id: The campus ID of the individual which to get
            clearance assignment permissions.

        Returns:
            A list of clearance IDs which of clearances that can be
            assigned by this individual.
        """
        record: list[dict] = get_clearance_collection(
            "liaison-clearance-permissions"
        ).find_one({'campus_id': campus_id})
        if record is None:
            return []
        return record.get('clearance_ids', [])
