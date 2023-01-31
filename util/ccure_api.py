"""Handle common interactions with the CCURE api"""

import os
from datetime import datetime, timedelta
import requests
from util.singleton import Singleton


class CcureApi(Singleton):
    """Class for managing interactions with the CCURE api"""

    session_id = None
    session_id_expires = None

    base_url = os.getenv("CCURE_BASE_URL")
    ccure_username = os.getenv("CCURE_USERNAME")
    ccure_password = os.getenv("CCURE_PASSWORD")
    ccure_client_name = os.getenv("CCURE_CLIENT_NAME")
    ccure_client_version = os.getenv("CCURE_CLIENT_VERSION")

    @classmethod
    def get_session_id(cls):
        """
        Get a session_id for a ccure api session
        :return str: the session_id
        """
        now = datetime.now()
        if cls.session_id is None or cls.session_id_expires <= now:
            login_route = "/victorwebservice/api/Authenticate/Login"
            response = requests.post(
                cls.base_url + login_route,
                data={
                    "UserName": cls.ccure_username,
                    "Password": cls.ccure_password,
                    "ClientName": cls.ccure_client_name,
                    "ClientVersion": cls.ccure_client_version,
                    "ClientID": ""
                },
                timeout=5000
            )
            login_session_id = response.headers["session-id"]
            login_response = requests.post(
                cls.base_url + login_route,
                data={
                    "UserName": cls.ccure_username,
                    "Password": cls.ccure_password,
                    "ClientName": cls.ccure_client_name,
                    "ClientVersion": cls.ccure_client_version,
                    "ClientID": login_session_id
                },
                timeout=5000
            )
            cls.session_id = login_response.headers["session-id"]
            cls.session_id_expires = now + timedelta(seconds=899)
        return cls.session_id

    @classmethod
    def logout(cls):
        """Log out of the CCURE session"""
        logout_route = "/victorwebservice/api/Authenticate/Logout"
        return requests.post(
            cls.base_url + logout_route,
            headers={"session-id": cls.session_id},
            timeout=5000
        )

    @classmethod
    def get_campus_id_by_email(cls, email):
        """
        With a user's email address, get their campus_id
        :param str email: The user's email address
        :return str: The user's campus_id
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
            timeout=5000
        )
        if response.status_code == 200:
            return response.json()[0].get("Text1", "")
        return ""

    @classmethod
    def get_object_id(cls, campus_id):
        """
        With a user's campus_id, get their ccure ObjectID
        :param str campus_id: The user's campus ID
        :return str: The user's ccure ObjectID
        """
        session_id = cls.get_session_id()
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
                "session-id": session_id,
                "Access-Control-Expose-Headers": "session-id"
            },
            timeout=5000
        )
        if response.status_code == 200:
            return response.json()[0].get("ObjectID", "")
        return ""

    @classmethod
    def get_clearance(cls, clearance_guid: str) -> dict:
        """
        Get a clearance object from CCURE matching the given clearance_guid
        :param str clearance_guid: the GUID value of the clearance object
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
            timeout=5000
        )
        if response.status_code == 200 and response.json():
            return response.json()[1]
        return {}

    @classmethod
    def get_clearance_id(cls, clearance_guid: str) -> int:
        """
        With a clearance's guid, get its ccure ObjectID
        :returns int: ccure ObjectID
        """
        clearance = cls.get_clearance(clearance_guid)
        return clearance.get("ObjectID", 0)

    @classmethod
    def get_clearance_name(cls, clearance_guid: str) -> str:
        """
        With a clearance's guid, get its Name in ccure
        """
        clearance = cls.get_clearance(clearance_guid)
        return clearance.get("Name", "")

    @staticmethod
    def encode(data: dict):
        """
        Encode a dict of form data as a string
        :param dict data: data about the new clearanace assignment
        :returns str: the encoded data
        """
        def get_form_entries(data: dict, prefix: str = ""):
            """
            Convert the data dict into a list of form entries
            :param dict data: data about the new clearance assignment
            :returns list: a list of strings representing key/value pairs
            """
            entries = []
            for key, val in data.items():
                if isinstance(val, (int, str)):
                    if prefix:
                        entries.append(f"{prefix}[{key}]={val}")
                    else:
                        entries.append(f"{prefix}{key}={val}")
                elif isinstance(val, list):
                    for i, list_item in enumerate(val):
                        if isinstance(list_item, dict):
                            entries.extend(get_form_entries(
                                data=list_item,
                                prefix=prefix + f"{key}[{i}]"
                            ))
                        else:
                            entries.append(f"{prefix}[{key}][]={list_item}")
            return entries
        return "&".join(get_form_entries(data))

    @classmethod
    def assign_clearances(cls, config: list[dict]):
        """
        Assign clearances to users in CCURE
        :param list config: dicts with the data needed to assign the clearance
        """
        route = "/victorwebservice/api/Objects/PersistToContainer"

        # group assignments requests by assignee
        person_assignments = {assg['assignee_id']: [] for assg in config}
        for assignment in config:
            clearances = person_assignments[assignment["assignee_id"]]
            ccure_id = cls.get_clearance_id(assignment["clearance_guid"])
            if ccure_id:
                clearances.append(ccure_id)
        person_assignments = {cls.get_object_id(k): v
                              for k, v in person_assignments.items()}

        for assignee, clearance_ids in person_assignments.items():
            # assign the assignee their new clearances
            data = {
                "type": ("SoftwareHouse.NextGen.Common"
                         ".SecurityObjects.Personnel"),
                "ID": assignee,
                "Children": [{
                    "Type": ("SoftwareHouse.NextGen.Common"
                             ".SecurityObjects.PersonnelClearancePair"),
                    "PropertyNames": ["PersonnelID", "ClearanceID"],
                    "PropertyValues": [assignee, clearance_id]
                } for clearance_id in clearance_ids]
            }
            response = requests.post(
                cls.base_url + route,
                data=cls.encode(data),
                headers={
                    "session-id": cls.get_session_id(),
                    "Access-Control-Expose-Headers": "session-id",
                    "Content-Type": "application/x-www-form-urlencoded"
                },
                timeout=5000
            )
            if response.status_code != 200:
                print(f"Unable to assign clearances to user {assignee}.")
                print(f"{response.status_code}: {response.text}")

    @classmethod
    def revoke_clearances(cls, config: list[dict]):
        """
        Revoke clearances from users in CCURE
        :param list config: dicts with the data needed to revoke the clearance
        """
        # group revoke requests by assignee
        revocations = {item["assignee_id"]: [] for item in config}
        for revocation in config:
            clearances = revocations[revocation["assignee_id"]]
            ccure_id = cls.get_clearance_id(revocation["clearance_guid"])
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
                timeout=5000
            )
            if response.status_code == 404:
                print(f"Can't revoke clearances from user {assignee}.")
                print(("User does not have clearance(s) "
                       f"{', '.join(map(str, clearance_ids))}."))
                return
            elif response.status_code != 200:
                print(f"Unable to revoke clearances from user {assignee}.")
                print(f"{response.status_code}: {response.text}")
                return

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
                timeout=5000
            )
            if response.status_code != 200:
                print(f"Unable to revoke clearances from user {assignee}.")
                print(f"{response.status_code}: {response.text}")
