"""
Controller functions for clearance assignment operations.
"""

from typing import Union
from datetime import datetime
from fastapi import APIRouter, Response, Depends, status
import requests
from pydantic import BaseModel
from middleware.get_authorization import get_authorization
from util.auth_checker import AuthChecker
from models.clearance_assignment import ClearanceAssignment

router = APIRouter()


class ClearanceAssetRequestBody(BaseModel):
    """
    Model for the body of a request to get clearance assets.
    """
    clearance_ids: list[str]


class ClearanceAssignRequestBody(BaseModel):
    """
    Model for the body of a request to assign clearances.
    """
    assignees: list[str]
    clearance_ids: list[str]
    start_time: Union[datetime, None]
    end_time: Union[datetime, None]


class ClearanceAssignRevokeRequestBody(BaseModel):
    """
    Model for the body of a request to revoke clearance assignments.
    """
    assignees: list[str]
    clearance_ids: list[str]


@router.get('/{campus_id}', tags=['Assignments'], dependencies=[Depends(AuthChecker('clearance_assignment_read'))])
def get_assignments(response: Response, campus_id: str) -> dict:
    """
    Returns all active clearance assignments for an individual given a
    campus ID.

    Parameters:
        campus_id: The campus ID of the person for which to query
        clearance assignments.
    """
    try:
        assignments = ClearanceAssignment.get_assignments_by_assignee(campus_id)
    except requests.ConnectTimeout:
        response.status_code = 408
        print(f"Ccure timeout. Could not get assignments for {campus_id}")
        return {
            'assignments': [],
            'allowed': []
        }

    res = []
    for assignment in assignments:
        res.append({
            'id': assignment.clearance.__dict__['id'],
            'name': assignment.clearance.__dict__['name']
        })

    response.status_code = status.HTTP_200_OK
    return {
        'assignments': res,
        'allowed': res
    }


@router.post('/assign', tags=['Assignments'], dependencies=[Depends(AuthChecker('clearance_assignment_write'))])
def assign_clearances(response: Response,
                      body: ClearanceAssignRevokeRequestBody,
                      authorization: dict = Depends(get_authorization)) -> dict:
    """
    Assigns one or more clearances to one or more people.
    """
    assigner_campus_id = authorization.get('campus_id', '')
    results = ClearanceAssignment.assign(
        assigner_campus_id, body.assignees, body.clearance_ids)

    response.status_code = status.HTTP_200_OK
    return {
        'changes': results
    }


@router.post('/revoke', tags=['Assignments'], dependencies=[Depends(AuthChecker('clearance_assignment_write'))])
def revoke_assignments(response: Response,
                       body: ClearanceAssignRevokeRequestBody,
                       authorization: dict = Depends(get_authorization)) -> dict:
    """
    Revokes one or more clearances to one or more people.
    """
    assigner_campus_id = authorization.get('campus_id', '')

    results = ClearanceAssignment.revoke(
        assigner_campus_id, body.assignees, body.clearance_ids)

    response.status_code = status.HTTP_200_OK
    return {
        'changes': results
    }
