"""Controller functions for liaison-related operations"""

from auth_checker import AuthChecker
from clearance_service.models.clearance import Clearance
from clearance_service.models.personnel import Personnel
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

router = APIRouter()


class ChangePermissionRequestBody(BaseModel):
    """Request body model."""

    campus_id: str
    clearance_ids: list[str] = []


@router.get("", tags=["Liaison"], dependencies=[Depends(AuthChecker("liaison_read"))])
def get_liaison_permissions(response: Response, campus_id: str) -> dict:
    """
    Fetch all clearances a liaison is allowed to assign

    Parameters:
        campus_id: The campus ID of the liaison to query

    Returns: A dict whose value is a list of clearance GUIDs
    """
    liaison = Personnel(campus_id=campus_id)
    permissions = liaison.get_liaison_permissions()

    response.status_code = status.HTTP_200_OK
    return {"clearances": permissions}


@router.post("/assign", tags=["Liaison"], dependencies=[Depends(AuthChecker("liaison_read"))])
def assign_liaison_permissions(response: Response, body: ChangePermissionRequestBody) -> dict:
    """
    Assign clearance assignment permissions to a liaison

    Parameters:
        body: data on campus ids and clearances to assign
    """
    clearances = Clearance.get_by_guids(body.clearance_ids)
    liaison = Personnel.find_one(campus_id=body.campus_id)
    record = liaison.assign_liaison_permissions(clearances)

    del record["_id"]
    response.status_code = status.HTTP_200_OK
    return {"record": record}


@router.post("/revoke", tags=["Liaison"], dependencies=[Depends(AuthChecker("liaison_read"))])
def revoke_liaison_permissions(response: Response, body: ChangePermissionRequestBody):
    """
    Revoke clearance assignment permissions from a liaison

    Parameters:
        body: data on campus ids and clearances to revoke
    """
    liaison = Personnel.find_one(campus_id=body.campus_id)
    record = liaison.revoke_liaison_permissions(body.clearance_ids)

    del record["_id"]
    response.status_code = status.HTTP_200_OK
    return {"record": record}
