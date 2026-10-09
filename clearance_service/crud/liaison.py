"""Controller functions for liaison-related operations"""

from datetime import datetime, timezone

from auth_checker import AuthChecker, TokenPayload
from clearance_service.models.clearance import Clearance
from clearance_service.models.personnel import Personnel
from clearance_service.util.authorization import get_authorization
from clearance_service.util.authorization_roles import PERMISSIONS
from clearance_service.util.handle_requests import RequestException
from fastapi import APIRouter, Depends, Response, status
from fastapi.encoders import jsonable_encoder
from pydantic import BaseModel
from pymongo.errors import DuplicateKeyError, PyMongoError

router = APIRouter()


class ChangePermissionRequestBody(BaseModel):
    """Request body model."""

    email: str
    clearance_ids: list[int] = []


class RemoveLiaisonRequestBody(BaseModel):
    email: str


@router.get(
    "", tags=["Liaison"], dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_LIAISON_READ"]))]
)
def get_liaison_permissions(email: str) -> dict:
    """
    Fetch all clearances a liaison is allowed to assign

    Parameters:
        email: The email address of the liaison to query

    Returns: A dict whose value is a list of clearance IDs
    """
    liaison = Personnel({"EmailAddress": email})
    permissions = liaison.get_liaison_permissions()
    return {"clearances": jsonable_encoder(permissions)}


@router.post(
    "/assign",
    tags=["Liaison"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_LIAISON_WRITE"]))],
)
def assign_liaison_permissions(response: Response, body: ChangePermissionRequestBody) -> dict:
    """
    Assign clearance assignment permissions to a liaison

    Parameters:
        body: data on liaisons and clearances to assign
    """
    if len(body.clearance_ids) == 0:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"record": {}, "detail": "At least one clearance is required to assign a clearance."}

    try:
        clearances = Clearance.get_by_ids(body.clearance_ids)
        liaison = Personnel.find_one(email=body.email, properties=[])
    except RequestException as e:
        response.status_code = e.status_code
        return {"record": {}, "detail": "Could not assign permissions"}
    except RuntimeError as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_message = "Could not assign permissions"
        if str(e) == "At least one clearance ID is required.":
            response.status_code = status.HTTP_400_BAD_REQUEST
            error_message = "At least one clearance is required to assign a clearance."
        return {"record": {}, "detail": error_message}

    if liaison is None:
        return {"record": None}
    record = liaison.assign_liaison_permissions(clearances)
    del record["_id"]
    return {"record": record}


@router.post(
    "/revoke",
    tags=["Liaison"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_LIAISON_WRITE"]))],
)
def revoke_liaison_permissions(response: Response, body: ChangePermissionRequestBody):
    """
    Revoke clearance assignment permissions from a liaison

    Parameters:
        body: data on liaisons and clearances to revoke
    """
    try:
        liaison = Personnel.find_one(email=body.email, properties=[])
    except RequestException as e:
        response.status_code = e.status_code
        return {"record": {}, "detail": "Could not revoke permissions"}

    if liaison is None:
        return {"record": None}
    record = liaison.revoke_liaison_permissions([int(_id) for _id in body.clearance_ids])
    del record["_id"]
    return {"record": record}


@router.post(
    "/add",
    tags=["Liaison"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_LIAISON_WRITE"]))],
)
def add_liaison(response: Response, body: RemoveLiaisonRequestBody) -> dict:
    """Add a liaison to the database."""
    try:
        new_liaison = Personnel.add_liaison(email=body.email)
    except DuplicateKeyError:
        response.status_code = status.HTTP_200_OK
        return {
            "updated": {"email": body.email},
            "detail": "This person is already in the liaison collection.",
        }
    except PyMongoError as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail": f"Could not add liaison to the database: {e}"}
    if new_liaison is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {
            "updated": None,
            "detail": f"Unable to find liaison {body.email} in ACS",
        }
    response.status_code = status.HTTP_201_CREATED
    return {"updated": vars(new_liaison), "detail": ""}


@router.post(
    "/remove",
    tags=["Liaison"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_LIAISON_WRITE"]))],
)
def remove_liaison(
    response: Response,
    body: RemoveLiaisonRequestBody,
) -> dict:
    """Remove a liaison's data from the database."""
    try:
        result = Personnel.remove_liaison(email=body.email)
    except PyMongoError as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail": f"Could not remove liaison from the database: {e}"}
    return {"updated": result}


@router.get(
    "/doors",
    tags=["Liaison"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_LIAISON_READ"]))],
)
def get_doors(
    response: Response,
    account: TokenPayload = Depends(get_authorization),
):
    """Get all doors assignable by the current user"""
    try:
        return sorted(Personnel.get_doors(account.email), key=lambda item: item.name)
    except RequestException as e:
        response.status_code = e.status_code
        return {"detail": f"Could not get doors for user {account.email}: {e}"}
