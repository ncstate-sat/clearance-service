"""
Database model to interact with a MongoDB database for the Clearance model
"""

from util.db_connect import get_clearance_collection


class ClearanceDB:
    """Plugin model to interface with MongoDB"""

    @staticmethod
    def get_clearance_permissions_by_campus_id(campus_id: str) -> list[str]:
        """
        Get a list of clearances a liaison has permission to assign

        Parameters:
            campus_id: The liaison's campus ID

        Returns: A list of GUIDs for the clearances that can be
            assigned by this individual.
        """
        record: list[dict] = get_clearance_collection(
            "liaison-clearance-permissions-new"
        ).find_one({"campus_id": campus_id})
        if record is None:
            return []
        return record.get("clearance_ids", [])
