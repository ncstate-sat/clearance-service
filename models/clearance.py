"""Model for Clearances"""

from typing import Optional
import requests
from util.ccure_api import CcureApi
from util.db_connect import get_clearance_collection


class Clearance:
    """
    A collection of assets and permissions for when access to them
    is granted
    """

    def __init__(self,
                 _id: str,
                 ccure_id: Optional[str] = None,
                 name: Optional[str] = None) -> None:
        """
        Parameters:
            _id: the GUID of the clearance as it is in CCure
            ccure_id: the ObjectID of the clearance in CCure
            name: the name of the clearance in CCure
        """
        self.id = _id
        self.ccure_id = ccure_id
        if name:
            self.name = name
        else:
            self.name = CcureApi.get_clearance_name(_id)

    @staticmethod
    def get(query: Optional[str] = "") -> list["Clearance"]:
        """
        Query a list of clearances

        Parameters:
            query: A regex string matching clearance names.
                Default to matching everything.

        Returns: A list of clearance objects
        """
        route = "/victorwebservice/api/v2/Personnel/ClearancesForAssignment"
        url = CcureApi.base_url + route
        request_json = {
            "partitionList": [],
            "whereClause": f"Name LIKE '%{(query or '').strip()}%'",
            "pageSize": 0,
            "pageNumber": 1,
            "sortColumnName": "",
            "whereArgList": [],
            "propertyList": ["Name"],
            "explicitPropertyList": []
        }
        response = requests.post(
            url,
            json=request_json,
            headers={
                "session-id": CcureApi.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == 200:
            clearances = response.json()[1:]
            return [Clearance(_id=clearance.get("GUID", ""),
                              name=clearance.get("Name", ""))
                    for clearance in clearances]
        print(response.text)
        return []

    @classmethod
    def get_all(cls) -> list["Clearance"]:
        """
        Get a list of all clearances

        Returns: A list of clearance objects
        """
        return cls.get()

    @staticmethod
    def get_by_guids(guids: list[str]) -> list[dict]:
        """
        Get a list of clearance records for use in the
        liaison-clearance-permissions collection

        Parameters:
            guids: list of clearance guids to get data for

        Returns: list of dicts including the guid, id, and name
            of the given clearances
        """
        route = "/victorwebservice/api/v2/Personnel/ClearancesForAssignment"
        url = CcureApi.base_url + route
        request_json = {
            "partitionList": [],
            "whereClause": " OR ".join(f"GUID = '{guid}'" for guid in guids),
            "pageSize": 0,
            "pageNumber": 1,
            "sortColumnName": "",
            "whereArgList": [],
            "propertyList": ["Name"],
            "explicitPropertyList": []
        }
        response = requests.post(
            url,
            json=request_json,
            headers={
                "session-id": CcureApi.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == 200:
            clearances = response.json()[1:]
            return [{
                "guid": clearance["GUID"],
                "id": clearance["ObjectID"],
                "name": clearance["Name"]
            } for clearance in clearances]
        print(response.text)
        return []

    @staticmethod
    def get_allowed(email: Optional[str] = None,
                    search: str = "") -> list["Clearance"]:
        """
        Get all clearances a liaison can assign

        Parameters:
            email: address of the liaison whose permissions are being checked
            search: only return clearances whose names include this substring

        Returns: A list of allowed Clearance objects
        """
        if not email:
            raise RuntimeError("An email address is required.")

        collection = get_clearance_collection("liaison-clearance-permissions")
        allowed_clearances = collection.aggregate([
            {
                "$match": {"email": email}
            },
            {
                "$unwind": "$clearances"
            },
            {
                "$project": {
                    "_id": "$clearances.guid",
                    "name": "$clearances.name",
                    "ccure_id": "$clearances.id"
                }
            },
            {
                "$match": {
                    "name": {
                        "$regex": search,
                        "$options": "i"  # case insensitive
                    }
                }
            }
        ])

        return [Clearance(**clearance) for clearance in allowed_clearances]

    @classmethod
    def verify_permission(cls,
                          clearance_id: str,
                          campus_id: str) -> bool:
        """
        Return whether or not a clearance can be assigned by an individual

        Parameters:
            clearance_id: the clearance's GUID
            campus_id: the individual's campus ID
        """
        allowed_guids = map(
            lambda clearance: clearance.id,
            cls.get_allowed(campus_id)
        )
        return clearance_id in allowed_guids
