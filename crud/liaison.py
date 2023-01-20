"""
Controller functions for liaison-related operations.
"""

from pydantic import BaseModel
from fastapi import APIRouter, Response, Depends, status
from util.auth_checker import AuthChecker
from models.personnel import Personnel

router = APIRouter()


class ChangePermissionRequestBody(BaseModel):
    """Request body model."""
    campus_id: str
    clearance_ids: list[str] = []


@router.get('', tags=['Liaison'],
            dependencies=[Depends(AuthChecker('liaison_read'))])
def get_liaison_permissions(response: Response, campus_id: str):
    """
    Fetches clearances which liaisons are allowed to assign.

    Parameters:
        campus_id: The Campus ID of the liaison to query.
    """
    liaison = Personnel(campus_id=campus_id)
    permissions = liaison.get_liaison_permissions()

    response.status_code = status.HTTP_200_OK
    return {
        'clearances': permissions
    }


@router.post('/assign', tags=['Liaison'],
             dependencies=[Depends(AuthChecker('liaison_read'))])
def assign_liaison_permissions(response: Response,
                               body: ChangePermissionRequestBody):
    """
    Assigns clearance assignment permissions to a liaison.
    """
    liaison = Personnel(campus_id=body.campus_id)
    record = liaison.assign_liaison_permissions(body.clearance_ids)

    del record['_id']
    response.status_code = status.HTTP_200_OK
    return {
        'record': record
    }


@router.post('/revoke', tags=['Liaison'],
             dependencies=[Depends(AuthChecker('liaison_read'))])
def revoke_liaison_permissions(response: Response,
                               body: ChangePermissionRequestBody):
    """
    Revokes clearance assignment permissions from a liaison.
    """
    liaison = Personnel(campus_id=body.campus_id)
    record = liaison.revoke_liaison_permissions(body.clearance_ids)

    del record['_id']
    response.status_code = status.HTTP_200_OK
    return {
        'record': record
    }
