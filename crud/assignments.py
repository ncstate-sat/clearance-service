"""Controller functions for clearance assignment operations."""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Response, Depends, status
import requests
from pydantic import BaseModel
from auth_checker import AuthChecker
from util.authorization import get_authorization, user_is_admin
from models.clearance_assignment import ClearanceAssignment
from models.clearance import Clearance

router = APIRouter()


class ClearanceAssetRequestBody(BaseModel):
    """Model for the body of a request to get clearance assets."""
    clearance_ids: list[str]


class ClearanceAssignRequestBody(BaseModel):
    """Model for the body of a request to assign clearances."""
    assignees: list[str]
    clearance_ids: list[str]
    start_time: Optional[datetime]
    end_time: Optional[datetime]


class ClearanceAssignRevokeRequestBody(BaseModel):
    """Model for the body of a request to revoke clearance assignments."""
    assignees: list[str]
    clearance_ids: list[str]


@router.get("/{campus_id}", tags=["Assignments"],
            dependencies=[Depends(AuthChecker("clearance_assignment_read"))])
def get_assignments(response: Response,
                    campus_id: str,
                    jwt_payload: dict = Depends(get_authorization)) -> dict:
    """
    Return all active clearance assignments for an individual given a
    campus ID.

    Parameters:
        campus_id: The campus ID of the person for which to query
            clearance assignments

    Returns:
        list of the individual's assignments, each with name, guid, and
            whether the user is authorized to revoke it
    """
    try:
        assignments = ClearanceAssignment.get_assignments_by_assignee(campus_id)
    except requests.ConnectTimeout:
        response.status_code = status.HTTP_408_REQUEST_TIMEOUT
        print(f"CCure timeout. Could not get assignments for {campus_id}")
        return {"assignments": []}

    all_assignments = []
    if user_is_admin(jwt_payload):
        for assignment in assignments:
            all_assignments.append({
                "id": assignment.clearance.id,
                "name": assignment.clearance.name,
                "can_revoke": True
            })
    else:
        assigner_email = jwt_payload.get("email", "")
        allowed_clearances = Clearance.get_allowed(assigner_email)
        allowed_ids = [clearance.id for clearance in allowed_clearances]

        for assignment in assignments:
            all_assignments.append({
                "id": assignment.clearance.id,
                "name": assignment.clearance.name,
                "can_revoke": assignment.clearance.id in allowed_ids
            })


    response.status_code = status.HTTP_200_OK
    return {"assignments": all_assignments}


@router.post("/assign", tags=["Assignments"],
             dependencies=[Depends(AuthChecker("clearance_assignment_write"))])
def assign_clearances(response: Response,
                      body: ClearanceAssignRevokeRequestBody,
                      jwt_payload: dict = Depends(get_authorization)) -> dict:
    """
    Assign one or more clearances to one or more people

    Parameters
        body: data on the assignees and clearances to be assigned
    """
    assigner_email = jwt_payload.get("email", "")
    if assigner_email is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail": "There must be an email address in this token."}

    if user_is_admin(jwt_payload):
        assign_ids = body.clearance_ids
    else:
        allowed_clearances = Clearance.get_allowed(assigner_email)
        allowed_ids = [clearance.id for clearance in allowed_clearances]
        assign_ids = [_id for _id in body.clearance_ids if _id in allowed_ids]
        if len(assign_ids) != len(body.clearance_ids):
            response.status_code = status.HTTP_403_FORBIDDEN
            return {
                "changes": 0,
                "detail": "Not authorized to assign all selected clearances"
            }

    try:
        assignment_count = ClearanceAssignment.assign(
            assigner_email, body.assignees, assign_ids)
    except KeyError:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {
            "changes": 0,
            "detail": "At least one of these clearances does not exist."
        }

    response.status_code = status.HTTP_200_OK
    return {"changes": assignment_count}


@router.post("/revoke", tags=["Assignments"],
             dependencies=[Depends(AuthChecker("clearance_assignment_write"))])
def revoke_clearances(response: Response,
                      body: ClearanceAssignRevokeRequestBody,
                      jwt_payload: dict = Depends(get_authorization)) -> dict:
    """
    Revoke one or more clearances to one or more people

    Parameters
        body: data on the assignees and clearances to be revoked
    """
    assigner_email = jwt_payload.get("email", "")
    if assigner_email is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail": "There must be an email address in this token."}

    if user_is_admin(jwt_payload):
        revoke_ids = body.clearance_ids
    else:
        allowed_clearances = Clearance.get_allowed(assigner_email)
        allowed_ids = [clearance.id for clearance in allowed_clearances]
        revoke_ids = [_id for _id in body.clearance_ids if _id in allowed_ids]
        if len(revoke_ids) != len(body.clearance_ids):
            response.status_code = status.HTTP_403_FORBIDDEN
            return {
                "changes": 0,
                "detail": "Not authorized to revoke all selected clearances"
            }

    revoke_count = ClearanceAssignment.revoke(
        assigner_email, body.assignees, revoke_ids)

    response.status_code = status.HTTP_200_OK
    return {"changes": revoke_count}
