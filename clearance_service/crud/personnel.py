"""Controller functions for personnel operations"""
from typing import Literal

from acslib.base.search import BooleanOperators
from acslib.ccure.data_models import PersonnelCreateData
from auth_checker import AuthChecker
from clearance_service.models import acs, filters
from clearance_service.models.personnel import Personnel
from clearance_service.util.authorization_roles import PERMISSIONS
from clearance_service.util.handle_requests import RequestException
from clearance_service.util.parse_list_param import parse_list_param
from fastapi import APIRouter, Depends, Response, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel

router = APIRouter()


class BulkPersonnelSearchBody(BaseModel):
    """Model for the body of a request to search for bulk personnel."""

    emails: list[str]


class PersonnelPersistRequestBody(BaseModel):
    """Model for the body of a request to add Personnel"""

    property_names: list[str]
    property_values: list


class PersonnelRemoveRequestBody(BaseModel):
    """Model for the body of a request to remove Personnel"""

    email: str


class SearchPersonnelBody(BaseModel):
    """Search people in the search_personnel endpoint"""

    search: str
    search_fields: dict[str, Literal["nfuzz", "fuzz", "rfuzz", "lfuzz"]]
    additional_display_properties: list[str] = []


@router.post(
    "",
    tags=["Personnel"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_PERSONNEL_READ"]))],
)
def search_personnel(
    response: Response,
    body: SearchPersonnelBody,
) -> dict:
    """
    Search all personnel

    Parameters:
        search: Search terms, searching name and email
        properties: Additional personnel properties to include in the response
    """
    if not body.search_fields:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"personnel": [], "detail": "`search_fields` is required."}
    try:
        personnel = Personnel.search(
            body.search,
            body.search_fields,
            body.additional_display_properties,
        )
    except RequestException as e:
        response.status_code = e.status_code
        return {"personnel": [], "detail": "Could not search personnel"}

    serialized_personnel = [vars(person) for person in personnel]
    return {"personnel": serialized_personnel}


@router.post(
    "/bulk",
    tags=["Personnel"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_PERSONNEL_READ"]))],
)
def search_bulk_personnel(
    response: Response,
    body: BulkPersonnelSearchBody,
    properties: list[str] = Depends(parse_list_param),
) -> dict:
    """
    Get information for personnel with a list of email addresses

    Parameters:
        emails: A list of email addresses to search on
        properties: Additional personnel properties to include in the response

    Returns:
        A list of found personnel and a list of values for which no value was found.
    """
    try:
        personnel = Personnel.search_by_email(body.emails, properties)
    except RequestException as e:
        response.status_code = e.status_code
        return {"personnel": [], "detail": "Could not search personnel"}

    not_found = body.emails
    for p in personnel:
        if p.email in not_found:
            not_found.remove(p.email)
        if (email_base := p.email.split("@")[0]) in not_found:
            not_found.remove(email_base)

    response.status_code = status.HTTP_200_OK
    return {"personnel": jsonable_encoder(personnel), "not_found": not_found}


@router.get(
    "/{email}",
    tags=["Personnel"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_PERSONNEL_READ"]))],
)
def get_person(
    response: Response,
    email: str,
    properties: list[str] = Depends(parse_list_param),
) -> dict:
    """
    Get one person's data by their email address

    Parameters:
        email: The email address of the person in question.
        properties: Additional personnel properties to return in the response

    Returns:
        JSON representation of the person, including requested additional properties
    """
    try:
        person = Personnel.find_one(email, properties)
    except RequestException as e:
        response.status_code = e.status_code
        return {"person": None, "detail": "Could not search personnel"}

    response.status_code = status.HTTP_200_OK
    return {"person": jsonable_encoder(person)}


@router.post(
    "/disable",
    tags=["Personnel"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_PERSONNEL_WRITE"]))],
)
def disable_personnel(response: Response, email: str) -> dict:
    """
    Disable a person in acs.

    Parameters:
        email: email address of the person to disable
    """
    try:
        personnel_filter = filters.PersonnelFilter(
            lookups={"EmailAddress": filters.NFUZZ},
            display_properties=["ObjectID"],
        )
        personnel_response = acs.personnel.search(terms=[email], search_filter=personnel_filter)
        if not personnel_response:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {
                "status": str(response.status_code),
                "message": f"Could not locate person with email address {email}.",
            }
        personnel_object_id = personnel_response[0].get("ObjectID")
        if personnel_object_id:
            acs.personnel.update(personnel_object_id, {"Disabled": True})
        else:
            response.status_code = status.HTTP_404_NOT_FOUND
            return {
                "status": str(response.status_code),
                "message": "Could not find personnel.",
            }
    except RequestException as e:
        response.status_code = e.status_code
        return {
            "status": str(response.status_code),
            "message": "Could not disable person.",
        }

    return {
        "status": str(response.status_code),
        "message": "Successfully disabled person.",
    }


@router.post(
    "/persist",
    tags=["Personnel"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_PERSONNEL_WRITE"]))],
)
def persist_personnel(response: Response, body: PersonnelPersistRequestBody) -> dict:
    """
    Persist a person to acs

    Parameters:
        property_names: columns of person record
        property_values: values of person record
    """
    linked_data = dict(zip(body.property_names, body.property_values))
    new_person_data = PersonnelCreateData(**linked_data)

    try:
        response = acs.personnel.create(new_person_data)
        return {
            "status": f"{response.status_code}",
            "message": "Successfully persisted person to ACS.",
        }
    except RequestException as e:
        response.status_code = e.status_code
        return {
            "status": f"{response.status_code}",
            "message": "Could not persist person to CCURE.",
        }


@router.post(
    "/update-credentials",
    tags=["Personnel"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_PERSONNEL_WRITE"]))],
)
def update_personnel_credentials(response: Response, email: str, new_credential: str) -> dict:
    """
    Update a person's credentials to ACS

    Parameters:
        email: email address of person to be updated
        credential: credential to be updated for person
    """
    try:
        # check if they exist in ccure
        search_filter = filters.PersonnelFilter(lookups={"EmailAddress": filters.NFUZZ})
        search_result = acs.personnel.search([email], search_filter=search_filter)
        if len(search_result) != 1:
            raise RuntimeError(
                "User does not exist in CCURE, ensure they do before pushing their credential"
            )

        object_id = search_result[0]["ObjectID"]

        # check if they have an existing credential
        existing_credential = acs.credential.search(
            terms=[object_id],
            search_filter=filters.CcureFilter(
                lookups={"PersonnelID": filters.NFUZZ},
                outer_bool=BooleanOperators.OR,
                display_properties=["ObjectID", "PersonnelID", "CardNumber"],
            ),
        )

        # if they do, update it
        if existing_credential:
            credential_response = acs.credential.update(
                existing_credential[0]["ObjectID"], {"CardNumber": new_credential}
            )
            return {
                "status": f"{credential_response.status_code}",
                "message": f"Updated credential for user {email}",
            }

        # if not, create it for the first time
        else:
            # TODO use credential create method instead of personnel.add_children method
            # new_credential_data = CredentialCreateData(**{"CardNumber": new_credential,
            # "CHUID": new_credential})
            # credential_response = acs.credential.create(object_id, new_credential_data)

            credential_response = acs.action.personnel.add_children(
                "SoftwareHouse.NextGen.Common.SecurityObjects.Personnel",
                object_id,
                "SoftwareHouse.NextGen.Common.SecurityObjects.Credential",
                [
                    {
                        "CardNumber": new_credential,
                        "CHUID": new_credential,
                    }
                ],
            )

            return {
                "status": f"{credential_response.status_code}",
                "message": f"Created credential for user {email}",
            }

    except RequestException as e:
        credential_response.status_code = e.status_code
        return {
            "status": f"{response.status_code}",
            "message": f"Could not update or create credential for user {email}",
        }
        # if they don't exist in ccure, throw an error
    except RuntimeError as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"status": 400, "message": str(e)}


@router.post(
    "/remove",
    tags=["Personnel"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_PERSONNEL_WRITE"]))],
)
def remove_personnel(response: Response, body: PersonnelRemoveRequestBody) -> dict:
    """
    Removes a person from ccure

    Parameters:
        email: email address of the person to remove
    """
    try:
        search_filter = filters.PersonnelFilter(lookups={"EmailAddress": filters.NFUZZ})
        search_result = acs.personnel.search([body.email], search_filter=search_filter)
        if (results_count := len(search_result)) != 1:
            raise RuntimeError(f"Found {results_count} people with the email address {body.email}")

        object_id = search_result[0]["ObjectID"]
        acs.personnel.delete(object_id)
        return {
            "message": "Successfully removed person from CCURE.",
        }
    except RequestException as e:
        response.status_code = e.status_code
        return {
            "status": f"{response.status_code}",
            "message": "Could not remove person from CCURE.",
        }
    except RuntimeError as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"status": status.HTTP_400_BAD_REQUEST, "message": str(e)}
