"""Controller functions for auditing and record endpoints"""

from typing import Optional
from dateutil import parser
from fastapi import APIRouter, Response, Depends, status
from auth_checker import AuthChecker
from models.audit import Audit

router = APIRouter()


@router.get("/", tags=["Audit"],
            dependencies=[Depends(AuthChecker("audit_read"))])
def search_actions(
    response: Response,
    assignee_id: Optional[str] = None,
    assigner_id: Optional[str] = None,
    clearance_id: Optional[str] = None,
    clearance_name: str = "",
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    page: int = 0,
    limit: int = 50
) -> dict:
    """
    Return the history of clearance assignments.
    Can filter by assignee, assigner, clearance_id, clearance name, or time
    """
    if from_time is not None:
        from_time = parser.parse(from_time)
    if to_time is not None:
        to_time = parser.parse(to_time)

    assignment_history = Audit.get_audit_log(
        assignee_id=assignee_id,
        assigner_id=assigner_id,
        clearance_id=clearance_id,
        clearance_name=clearance_name,
        from_time=from_time,
        to_time=to_time,
        page=page,
        limit=limit
    )

    response.status_code = status.HTTP_200_OK
    return {'assignments': assignment_history}
