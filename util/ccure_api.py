"""Handle common interactions with the CCure api"""

import os
from typing import Optional
from fastapi import status
from pydantic import BaseModel
import requests
from .encode_form_data import encode


class CcureApi:
    """Class for managing interactions with the CCure api"""

    base_url = os.getenv("CCURE_BASE_URL")
    session_id = None

    @classmethod
    def get_session_id(cls) -> str:
        """
        Get a session_id for a CCure api session

        Returns: the session_id
        """
        if cls.session_id is None:
            login_route = "/victorwebservice/api/Authenticate/Login"
            response = requests.post(
                cls.base_url + login_route,
                data={
                    "UserName": os.getenv("CCURE_USERNAME"),
                    "Password": os.getenv("CCURE_PASSWORD"),
                    "ClientName": os.getenv("CCURE_CLIENT_NAME"),
                    "ClientVersion": os.getenv("CCURE_CLIENT_VERSION"),
                    "ClientID": os.getenv("CCURE_CLIENT_ID")
                },
                timeout=1
            )
            cls.session_id = response.headers["session-id"]
        return cls.session_id

    @classmethod
    def session_keepalive(cls):
        """
        Prevent the CCure api session from expiring from inactivity.
        Runs every minute in the scheduler.
        """
        keepalive_route = "/victorwebservice/api/v2/session/keepalive"
        response = requests.post(
            cls.base_url + keepalive_route,
            headers={
                "session-id": cls.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code != status.HTTP_200_OK:
            print("CCure keepalive error:", response.status_code, response.text)
            cls.logout()

    @classmethod
    def logout(cls):
        """Log out of the CCure session"""
        logout_route = "/victorwebservice/api/Authenticate/Logout"
        response = requests.post(
            cls.base_url + logout_route,
            headers={"session-id": cls.get_session_id()},
            timeout=1
        )
        cls.session_id = None
        if response.status_code == 200:
            return {"success": True}
        return {"success": False}

    @classmethod
    def get_campus_id_by_email(cls, email) -> str:
        """
        With an individual's email address, get their campus_id

        Parameters:
            email: The individual's email address
        """
        route = "/victorwebservice/api/Objects/FindObjsWithCriteriaFilter"
        url = cls.base_url + route
        request_json = {
            "TypeFullName": "Personnel",
            "WhereClause": f"Text14 = '{email}'"
        }
        response = requests.post(
            url,
            json=request_json,
            headers={
                "session-id": cls.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == status.HTTP_200_OK:
            if (json := response.json()):
                return json[0].get("Text1", "")
        return ""

    @classmethod
    def get_person_object_id(cls, campus_id: str) -> int:
        """
        With a person's campus_id, get their CCure ObjectID

        Parameters:
            campus_id: The person's campus ID
        """
        route = "/victorwebservice/api/Objects/FindObjsWithCriteriaFilter"
        url = cls.base_url + route
        request_json = {
            "TypeFullName": "Personnel",
            "WhereClause": f"Text1 = '{campus_id}'"
        }
        response = requests.post(
            url,
            json=request_json,
            headers={
                "session-id": cls.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == status.HTTP_200_OK:
            return response.json()[0].get("ObjectID", 0)
        return 0

    @classmethod
    def get_person_object_ids(cls, campus_ids: set[str]) -> dict:
        """
        Map people's campus IDs to their CCure IDs

        Parameters:
            campus_ids: the IDs of the people to include

        Returns: dict in the format {campus_id: ccure_id}
        """
        if not campus_ids:
            return {}
        route = "/victorwebservice/api/Objects/FindObjsWithCriteriaFilter"
        url = cls.base_url + route
        request_json = {
            "TypeFullName": "Personnel",
            "WhereClause": " OR ".join(f"Text1 = '{campus_id}'"
                                       for campus_id in campus_ids)
        }
        response = requests.post(
            url,
            json=request_json,
            headers={
                "session-id": cls.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == status.HTTP_200_OK:
            return {person["Text1"]: person["ObjectID"]
                    for person in response.json()}
        return {}

    @classmethod
    def get_person_by_campus_id(cls, campus_id: str) -> dict:
        """
        Find one person by their campus ID

        Parameters:
            campus_id: the person's campus ID

        Returns: a dict with the person's details in CCure
        """
        query_route = "/victorwebservice/api/Objects/FindObjsWithCriteriaFilter"
        url = cls.base_url + query_route

        request_json = {
            "TypeFullName": "Personnel",
            "WhereClause": f"Text1 = '{campus_id}'"
        }
        response = requests.post(
            url,
            json=request_json,
            headers={
                "session-id": cls.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == status.HTTP_200_OK:
            return response.json()[0]
        print(response.text)
        return {}

    @classmethod
    def search_people(cls, search: str) -> list[dict]:
        """
        Get data on people matching all search terms
        Search by campus ID and email

        Parameters:
            search: the term or terms to search by

        Returns: list of dicts with person records
        """
        query_route = "/victorwebservice/api/Objects/FindObjsWithCriteriaFilter"
        url = cls.base_url + query_route
        search_terms = search.split()

        term_queries = [
            (f"(Text1 LIKE '%{term}%' OR "  # campus_id
             f"Text14 LIKE '%{term}%')")  # email
            for term in search_terms
        ]
        request_json = {
            "TypeFullName": "Personnel",
            "WhereClause": " AND ".join(term_queries)
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
        if response.status_code == status.HTTP_200_OK:
            return response.json()
        print(response.text)
        return []


    @classmethod
    def search_clearances(cls, query: str) -> list[dict]:
        """
        Find all clearances whose names match the query string

        Parameters:
            query: the string to search clearance names by

        Returns: list of dicts with data from all matching clearances
        """
        route = "/victorwebservice/api/v2/Personnel/ClearancesForAssignment"
        url = cls.base_url + route
        request_json = {
            "partitionList": [],
            "whereClause": f"Name LIKE '%{query}%'",
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
                "session-id": cls.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == status.HTTP_200_OK:
            return response.json()[1:]
        print(response.text)
        return []

    @classmethod
    def get_assigned_clearances(cls, assignee_id: int) -> int:
        """
        With a person's CCure ObjectID, get the clearances assigned to them

        Parameters:
            assignee_id: the person's ID in CCure
        """
        route = "/victorwebservice/api/Objects/GetAllWithCriteria"
        url = cls.base_url + route
        request_json = {
            "TypeFullName": ("SoftwareHouse.NextGen.Common.SecurityObjects."
                             "PersonnelClearancePairTimed"),
            "WhereClause": f"PersonnelID = {assignee_id}"
        }
        return requests.post(
            url,
            json=request_json,
            headers={
                "session-id": cls.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )

    @classmethod
    def get_clearance_by_guid(cls, clearance_guid: str) -> dict:
        """
        Get a clearance object from CCure matching the given clearance_guid

        Parameters:
            clearance_guid: the GUID value of the clearance object
        """
        route = "/victorwebservice/api/v2/Personnel/ClearancesForAssignment"
        url = cls.base_url + route
        request_json = {
            "partitionList": [],
            "whereClause": f"GUID = '{clearance_guid}'",
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
                "session-id": cls.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == status.HTTP_200_OK and response.json():
            return response.json()[1]
        return {}

    @classmethod
    def get_clearances_by_guid(cls, clearance_guids: list[str]) -> list[dict]:
        """
        Get clearance objects from CCure matching the given clearance_guids

        Parameters:
            clearance_guids: the GUID values of the clearance objects
        """
        route = "/victorwebservice/api/v2/Personnel/ClearancesForAssignment"
        url = cls.base_url + route
        request_json = {
            "partitionList": [],
            "whereClause": " OR ".join(f"GUID = '{guid}'" for guid in clearance_guids),
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
                "session-id": cls.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == status.HTTP_200_OK and response.json():
            return response.json()[1:]
        print(response.text)
        return []

    @classmethod
    def get_clearances_by_id(cls, clearance_ids: list[int]) -> list[dict]:
        """
        Get clearance objects matching a list of CCure clearance ObjectIDs

        Parameters:
            clearance_ids: IDs for all the clearances to retrieve
        """
        route = "/victorwebservice/api/v2/Personnel/ClearancesForAssignment"
        query = " OR ".join(f"ObjectID = {_id}" for _id in clearance_ids)
        request_json = {
            "partitionList": [],
            "whereClause": query,
            "pageSize": 0,
            "pageNumber": 1,
            "sortColumnName": "",
            "whereArgList": [],
            "propertyList": ["Name"],
            "explicitPropertyList": []
        }
        response = requests.post(
            cls.base_url + route,
            json=request_json,
            headers={
                "session-id": cls.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        return response.json()[1:]

    @classmethod
    def get_clearance_id(cls, clearance_guid: str) -> int:
        """
        With a clearance's guid, get its CCure ObjectID

        Parameters:
            clearance_guid: the clearance's GUID value in CCure
        """
        clearance = cls.get_clearance_by_guid(clearance_guid)
        return clearance.get("ObjectID", 0)

    @classmethod
    def get_clearance_data(cls, clearance_guids: set[str]) -> dict:
        """
        Map clearance guids to their corresponding CCure IDs
        and clearance names

        Parameters:
            clearance_guids: the guids of the clearances to get data for

        Returns: dict with clearance guids as keys
        """
        route = "/victorwebservice/api/v2/Personnel/ClearancesForAssignment"
        url = cls.base_url + route
        request_json = {
            "partitionList": [],
            "whereClause": " OR ".join(f"GUID = '{clearance_guid}'"
                                       for clearance_guid in clearance_guids),
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
                "session-id": cls.get_session_id(),
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == status.HTTP_200_OK and response.json():
            return {
                clearance["GUID"]: {
                    "id": clearance["ObjectID"],
                    "name": clearance["Name"]
                } for clearance in response.json()[1:]
            }
        return {}

    @classmethod
    def get_clearance_name(cls, clearance_guid: str) -> str:
        """
        With a clearance's guid, get its name in CCure
        """
        clearance = cls.get_clearance_by_guid(clearance_guid)
        return clearance.get("Name", "")

    class AssignRevokeConfig(BaseModel):
        """For CCure assign_clearances and revoke_clearances methods"""
        assignee_id: str
        assigner_id: str
        clearance_guid: str
        message: Optional[str]
        activate: Optional[str]

    @classmethod
    def assign_clearances(cls, config: list[AssignRevokeConfig]):
        """
        Assign clearances to people in CCure

        Parameters:
            config: list of dicts with the data needed to assign the clearance
        """
        campus_ids = set()
        clearance_guids = set()
        for item in config:
            campus_ids.add(item.get("assignee_id"))
            clearance_guids.add(item.get("clearance_guid"))
        # then get ccure ids for assignee_ids and clearance_guids
        assignee_ids = cls.get_person_object_ids(campus_ids)
        clearances_data = cls.get_clearance_data(clearance_guids)
        # group assignments requests by assignee
        person_assignments = {assignee_id: []
                              for assignee_id in assignee_ids.values()}
        for assignment in config:
            assignee_id = assignee_ids[assignment["assignee_id"]]
            clearances = person_assignments[assignee_id]
            ccure_id = clearances_data[assignment["clearance_guid"]]
            if ccure_id:
                clearances.append(ccure_id)

        for assignee, clearances in person_assignments.items():
            # assign the assignee their new clearances
            data = {
                "type": ("SoftwareHouse.NextGen.Common"
                         ".SecurityObjects.Personnel"),
                "ID": assignee,
                "Children": [{
                    "Type": ("SoftwareHouse.NextGen.Common"
                             ".SecurityObjects.PersonnelClearancePair"),
                    "PropertyNames": ["PersonnelID", "ClearanceID"],
                    "PropertyValues": [assignee, clearance["id"]]
                } for clearance in clearances]
            }
            route = "/victorwebservice/api/Objects/PersistToContainer"
            response = requests.post(
                cls.base_url + route,
                data=encode(data),
                headers={
                    "session-id": cls.get_session_id(),
                    "Access-Control-Expose-Headers": "session-id",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                timeout=1
            )
            if response.status_code != status.HTTP_200_OK:
                print(f"Unable to assign clearances to person {assignee}.")
                print(f"{response.status_code}: {response.text}")
        return clearances_data

    @classmethod
    def revoke_clearances(cls, config: list[AssignRevokeConfig]):
        """
        Revoke clearances from people in CCure

        Parameters:
            config: list of dicts with the data needed to revoke the clearance
        """
        campus_ids = set()
        clearance_guids = set()
        for item in config:
            campus_ids.add(item.get("assignee_id"))
            clearance_guids.add(item.get("clearance_guid"))
        # then get ccure ids for assignee_ids and clearance_guids
        assignee_ids = cls.get_person_object_ids(campus_ids)
        clearances_data = cls.get_clearance_data(clearance_guids)

        # group revoke requests by assignee
        revocations = {item["assignee_id"]: [] for item in config}
        for revocation in config:
            clearances = revocations[revocation["assignee_id"]]
            ccure_id = clearances_data[revocation["clearance_guid"]]["id"]
            if ccure_id:
                clearances.append(ccure_id)
        revocations = {assignee_ids[k]: v for k, v in revocations.items()}

        for assignee, clearance_ids in revocations.items():
            # get object IDs of the assignee's PersonnelClearancePair objects
            clearance_query = " OR ".join(f"ClearanceID = {clearance_id}"
                                          for clearance_id in clearance_ids)

            route = "/victorwebservice/api/Objects/GetAllWithCriteria"
            response = requests.post(
                cls.base_url + route,
                json={
                    "TypeFullName": ("SoftwareHouse.NextGen.Common"
                                     ".SecurityObjects.PersonnelClearancePair"),
                    "WhereClause": (f"PersonnelID = {assignee} "
                                    f"AND ({clearance_query})")
                },
                headers={
                    "session-id": cls.get_session_id(),
                    "Access-Control-Expose-Headers": "session-id"
                },
                timeout=1
            )
            if response.status_code != status.HTTP_200_OK:
                print(f"Unable to revoke clearances from {assignee}.")
                print(f"{response.status_code}: {response.text}")
                return response

            assignment_ids = [pair["ObjectID"] for pair in response.json()]

            # delete the assignee's PersonnelClearancePair objects
            data = {
                "type": "SoftwareHouse.NextGen.Common"
                        ".SecurityObjects.Personnel",
                "ID": assignee,
                "Children": [{
                    "Type": ("SoftwareHouse.NextGen.Common"
                             ".SecurityObjects.PersonnelClearancePair"),
                    "ID": assignment_id
                } for assignment_id in assignment_ids]
            }
            route = "/victorwebservice/api/Objects/RemoveFromContainer"
            response = requests.post(
                cls.base_url + route,
                data=encode(data),
                headers={
                    "session-id": cls.get_session_id(),
                    "Access-Control-Expose-Headers": "session-id",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                timeout=1
            )
            if response.status_code != status.HTTP_200_OK:
                print(f"Unable to revoke clearances from {assignee}.")
                print(f"{response.status_code}: {response.text}")

        return clearances_data
