"""Model for Clearances"""

from typing import Optional
import requests
from plugins.database.clearance import ClearanceDB
from util.ccure_api import CcureApi


class Clearance:
    """
    A collection of assets and permissions for when access to them
    is granted
    """
    ccure_api = CcureApi()

    def __init__(self, _id: str, name: Optional[str] = None) -> None:
        """
        Parameters:
            _id: the GUID of the clearance as it is in CCure
            name: the name of the clearance in CCure
        """
        self.id = _id
        if name:
            self.name = name
        else:
            self.name = self.ccure_api.get_clearance_name(_id)

    @classmethod
    def get(cls, query: Optional[str] = "") -> list["Clearance"]:
        """
        Query a list of clearances

        Parameters:
            query: A regex string matching clearance names.
                Default to matching everything.

        Returns: A list of clearance objects
        """
        route = "/victorwebservice/api/v2/Personnel/ClearancesForAssignment"
        url = cls.ccure_api.base_url + route
        request_json = {
            "partitionList": [],
            "whereClause": f"Name LIKE '%{query or ''}%'",
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
                "session-id": cls.ccure_api.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == 200:
            clearances = response.json()[1:]
            return [Clearance(_id=clearance.get("GUID", ""))
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

    @classmethod
    def filter_allowed(cls,
                       clearances: list["Clearance"],
                       campus_id: Optional[str] = None,
                       email: Optional[str] = None) -> list["Clearance"]:
        """
        Filter out clearances which a person cannot assign from a given
        list of clearances

        Parameters:
            clearances: list of clearances to be filtered
            campus_id: the person whose permissions are to be checked
            email: alternate ID for the person whose permissions
                are to be checked

        Returns: A list of allowed Clearance objects
        """
        if campus_id is None and email is not None:
            campus_id = cls.ccure_api.get_campus_id_by_email(email)
        if campus_id:
            clearance_ids = ClearanceDB.get_clearance_permissions_by_campus_id(
                campus_id)
        else:
            raise RuntimeError("A campus_id or email address is required.")

        return [clearance for clearance in clearances
                if clearance.id in clearance_ids]

    @classmethod
    def get_allowed(cls,
                    campus_id: Optional[str] = None) -> list["Clearance"]:
        """
        Get a list of clearances allowed to be assigned by an individual

        Parameters:
            campus_id: the individual's campus id

        Returns: A list of Clearance objects
        """
        return cls.filter_allowed(cls.get_all(), campus_id=campus_id)

    @staticmethod
    def verify_permission(clearance_id: str,
                          campus_id: Optional[str] = None) -> bool:
        """
        Return whether or not a clearance can be assigned by an individual

        Parameters:
            clearance_id: the clearance's GUID
            campus_id: the individual's campus ID
        """
        if campus_id:
            clearance_ids = ClearanceDB.get_clearance_permissions_by_campus_id(
                campus_id)
        else:
            raise RuntimeError("A campus_id is required.")

        return clearance_id in clearance_ids
