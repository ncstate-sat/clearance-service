"""
Model for Clearances.
"""

from typing import Union, Optional
import requests
from plugins.database.clearance import ClearanceDB
from util.ccure_api import CcureApi


class Clearance:
    """
    A collection of assets and permissions for when access to them
    is granted.
    """
    ccure_api = CcureApi()

    def __init__(self, _id: str, name: Optional[str] = None) -> None:
        """
        :param str _id: the GUID of the clearance as it is in CCURE
        :param str name: the name of the clearance in CCURE
        """
        self.id = _id
        if name:
            self.name = name
        else:
            self.name = self.ccure_api.get_clearance_name(_id)

    @classmethod
    def get(cls, query: str | None = "") -> list["Clearance"]:
        """
        Queries a list of clearances.

        Parameters:
            query: A regex string matching clearance names.
                   Default to matching everything.

        Returns:
            A list of clearance objects.
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
            timeout=5000
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
        Gets a list of all clearances.

        Returns:
            A list of clearance objects.
        """
        return cls.get()

    @classmethod
    def filter_allowed(cls,
                       clearances: list["Clearance"],
                       campus_id: Union[str, None] = None,
                       email: Union[str, None] = None) -> list["Clearance"]:
        """
        Filters out clearances which a person cannot assign from a given
        list of clearances.
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
                    campus_id: Union[str, None] = None) -> list["Clearance"]:
        """
        Returns a list of clearances allowed to be assigned by an
        individual.
        """
        return cls.filter_allowed(cls.get_all(), campus_id=campus_id)

    @classmethod
    def verify_permission(cls,
                          clearance_id: str,
                          campus_id: Union[str, None] = None) -> bool:
        """
        Returns whether or not a clearance can be assigned by an individual.
        """
        if campus_id:
            clearance_ids = ClearanceDB.get_clearance_permissions_by_campus_id(
                campus_id)
        else:
            raise RuntimeError("A campus_id is required.")

        return clearance_id in clearance_ids
