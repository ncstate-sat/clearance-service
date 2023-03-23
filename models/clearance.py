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

    def __init__(self,
                 _id: str,
                 ccure_id: Optional[str] = None,
                 name: Optional[str] = None) -> None:
        """
        Parameters:
            _id: the GUID of the clearance as it is in CCure
            ccure_id: the ObjectID of the clearance in CCure
            name: the name of the clearance in CCure
        """  # TODO change these variable names. fix 'id'
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
    def filter_allowed(clearances: list["Clearance"],
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
            campus_id = CcureApi.get_campus_id_by_email(email)
        if campus_id:
            get_permissions = ClearanceDB.get_clearance_permissions_by_campus_id
            allowed_clearances = get_permissions(campus_id)
        else:
            raise RuntimeError("A campus_id or email address is required.")

        allowed_clearance_guids = [clearance["guid"]
                                   for clearance in allowed_clearances]
        return [clearance for clearance in clearances
                if clearance.id in allowed_clearance_guids]

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

        allowed_guids = [clearance["guid"] for clearance in clearance_ids]
        return clearance_id in allowed_guids
