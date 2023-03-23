"""Handle common interactions with the CCure api"""

import os
from typing import Optional
from pydantic import BaseModel
import requests


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
        print(cls.session_id)
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
        if response.status_code != 200:
            print("CCure keepalive error:", response.status_code, response.text)
            cls.logout()
            cls.session_id = None

    @classmethod
    def logout(cls):
        """Log out of the CCure session"""
        logout_route = "/victorwebservice/api/Authenticate/Logout"
        return requests.post(
            cls.base_url + logout_route,
            headers={"session-id": cls.get_session_id()},
            timeout=1
        )

    @classmethod
    def get_campus_id_by_email(cls, email) -> str:
        """
        With an individual's email address, get their campus_id

        Parameters:
            email: The individual's email address
        """
        session_id = cls.get_session_id()
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
                "session-id": session_id,
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == 200:
            return response.json()[0].get("Text1", "")
        return ""

    @classmethod
    def get_object_id(cls, campus_id: str) -> int:
        """
        With a user's campus_id, get their CCure ObjectID

        Parameters:
            campus_id: The user's campus ID
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
        if response.status_code == 200:
            return response.json()[0].get("ObjectID", 0)
        return 0

    @classmethod
    def get_object_ids(cls, campus_ids: set[str]) -> dict:
        """
        """
        if not campus_ids:
            return {}
        route = "/victorwebservice/api/Objects/FindObjsWithCriteriaFilter"
        url = cls.base_url + route
        request_json = {
            "TypeFullName": "Personnel",
            "WhereClause": " OR ".join(f"Text1 = '{campus_id}'" for campus_id in campus_ids)
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
        if response.status_code == 200:
            return {person["Text1"]: person["ObjectID"] for person in response.json()}
        return {}

    @classmethod
    def get_clearance(cls, clearance_guid: str) -> dict:
        """
        Get a clearance object from CCure matching the given clearance_guid

        Parameters:
            clearance_guid: the GUID value of the clearance object
        """
        session_id = cls.get_session_id()
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
                "session-id": session_id,
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=1
        )
        if response.status_code == 200 and response.json():
            return response.json()[1]
        return {}

    @classmethod
    def get_clearance_id(cls, clearance_guid: str) -> int:
        """
        With a clearance's guid, get its CCure ObjectID

        Parameters:
            clearance_guid: the clearance's GUID value in CCure
        """
        clearance = cls.get_clearance(clearance_guid)
        return clearance.get("ObjectID", 0)

    @classmethod
    def get_clearance_ids(cls, clearance_guids: set[str]) -> dict:
        """
        """
        route = "/victorwebservice/api/v2/Personnel/ClearancesForAssignment"
        url = cls.base_url + route
        request_json = {
            "partitionList": [],
            "whereClause": " OR ".join(f"GUID = '{clearance_guid}'" for clearance_guid in clearance_guids),
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
        if response.status_code == 200 and response.json():
            return {clearance["GUID"]: {"id": clearance["ObjectID"], "name": clearance["Name"]} for clearance in response.json()[1:]}
        return {}

    @classmethod
    def get_clearance_name(cls, clearance_guid: str) -> str:
        """
        With a clearance's guid, get its name in CCure
        """
        clearance = cls.get_clearance(clearance_guid)
        return clearance.get("Name", "")

    @staticmethod
    def encode(data: dict) -> str:
        """
        Encode a dict of form data as a string

        Parameters:
            data: data about the new clearanace assignment

        Returns: the string of encoded data
        """
        def get_form_entries(data: dict, prefix: str = "") -> list[str]:
            """
            Convert the data dict into a list of form entries

            Parameters:
                data: data about the new clearance assignment

            Returns: list of strings representing key/value pairs
            """
            entries = []
            for key, val in data.items():
                if isinstance(val, (int, str)):
                    if prefix:
                        entries.append(f"{prefix}[{key}]={val}")
                    else:
                        entries.append(f"{key}={val}")
                elif isinstance(val, list):
                    for i, list_item in enumerate(val):
                        if isinstance(list_item, dict):
                            entries.extend(get_form_entries(
                                data=list_item,
                                prefix=prefix + f"{key}[{i}]"
                            ))
                        elif prefix:
                            entries.append(f"{prefix}[{key}][]={list_item}")
                        else:
                            entries.append(f"{key}[]={list_item}")
            return entries

        return "&".join(get_form_entries(data))

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
        Assign clearances to users in CCure

        Parameters:
            config: list of dicts with the data needed to assign the clearance
        """
        # TODO take clearance data as an argument. don't do it here. (?)
        campus_ids = set()
        clearance_guids = set()
        for item in config:
            campus_ids.add(item.get("assignee_id"))
            clearance_guids.add(item.get("clearance_guid"))
        # then get ccure ids for assignee_ids and clearance_guids
        assignee_ids = cls.get_object_ids(campus_ids)
        clearances_data = cls.get_clearance_ids(clearance_guids)  # TODO clean. rename. whatever.
        # group assignments requests by assignee
        person_assignments = {assignee_id: [] for assignee_id in assignee_ids.values()}
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
                data=cls.encode(data),
                headers={
                    "session-id": cls.get_session_id(),
                    "Access-Control-Expose-Headers": "session-id",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                timeout=1
            )
            if response.status_code != 200:
                print(f"Unable to assign clearances to user {assignee}.")
                print(f"{response.status_code}: {response.text}")
        return clearances_data

    @classmethod
    def revoke_clearances(cls, config: list[AssignRevokeConfig]):
        """
        Revoke clearances from users in CCure

        Parameters:
            config: list of dicts with the data needed to revoke the clearance
        """
        # group revoke requests by assignee
        revocations = {item["assignee_id"]: [] for item in config}
        for revocation in config:
            clearances = revocations[revocation["assignee_id"]]
            ccure_id = cls.get_clearance_id(revocation["clearance_id"])
            if ccure_id:
                clearances.append(ccure_id)

        revocations = {cls.get_object_id(k): v for k, v in revocations.items()}

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
            if response.status_code == 404:
                print(f"Can't revoke clearances from user {assignee}.")
                print(("User does not have clearance(s) "
                       f"{', '.join(map(str, clearance_ids))}."))
                return response
            elif response.status_code != 200:
                print(f"Unable to revoke clearances from user {assignee}.")
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
                data=cls.encode(data),
                headers={
                    "session-id": cls.get_session_id(),
                    "Access-Control-Expose-Headers": "session-id",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                timeout=1
            )
            if response.status_code != 200:
                print(f"Unable to revoke clearances from user {assignee}.")
                print(f"{response.status_code}: {response.text}")
