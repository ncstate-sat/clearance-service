"""Controller functions for clearance assignment operations."""

from typing import Optional
from datetime import datetime
from fastapi import APIRouter, Response, Depends, status
import requests
from pydantic import BaseModel
from auth_checker import AuthChecker
from middleware.get_authorization import get_authorization
from models.clearance_assignment import ClearanceAssignment

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
def get_assignments(response: Response, campus_id: str) -> dict:
    """
    Return all active clearance assignments for an individual given a
    campus ID.

    Parameters:
        campus_id: The campus ID of the person for which to query
            clearance assignments

    Returns:
        A dict with the individual's own assignments and those they can assign
    """
    try:
        assignments = ClearanceAssignment.get_assignments_by_assignee(campus_id)
    except requests.ConnectTimeout:
        response.status_code = 408
        print(f"CCure timeout. Could not get assignments for {campus_id}")
        return {
            "assignments": [],
            "allowed": []
        }

    res = []
    for assignment in assignments:
        res.append({
            "id": assignment.clearance.id,
            "name": assignment.clearance.name
        })

    response.status_code = status.HTTP_200_OK
    return {
        "assignments": res,
        "allowed": res
    }


@router.post("/assign", tags=["Assignments"],
             dependencies=[Depends(AuthChecker("clearance_assignment_write"))])
def assign_clearances(response: Response,
                      body: ClearanceAssignRevokeRequestBody,
                      authorization: dict = Depends(get_authorization)) -> dict:
    """
    Assign one or more clearances to one or more people

    Parameters
        body: data on the assignees and clearances to be assigned
    """
    assigner_email = authorization.get("email", "")
    try:
        assignment_count = ClearanceAssignment.assign(
            assigner_email, body.assignees, body.clearance_ids)
    except KeyError:
        response.status_code = 400
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
                      authorization: dict = Depends(get_authorization)) -> dict:
    """
    Revoke one or more clearances to one or more people

    Parameters
        body: data on the assignees and clearances to be revoked
    """
    assigner_email = authorization.get("email", "")
    revoke_count = ClearanceAssignment.revoke(
        assigner_email, body.assignees, body.clearance_ids)

    response.status_code = status.HTTP_200_OK
    return {"changes": revoke_count}
