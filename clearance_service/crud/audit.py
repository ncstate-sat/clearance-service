"""Controller functions for auditing and record endpoints"""

from typing import Optional

from auth_checker import AuthChecker
from clearance_service.models.audit import Audit
from clearance_service.util.authorization_roles import PERMISSIONS
from dateutil import parser
from fastapi import APIRouter, Depends
from fastapi.encoders import jsonable_encoder

router = APIRouter()


@router.get(
    "", tags=["Audit"], dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_AUDIT_READ"]))]
)
def search_actions(
    assignee_email: Optional[str] = None,
    assigner_email: Optional[str] = None,
    clearance_id: Optional[int] = None,
    clearance_name: str = "",
    from_time: Optional[str] = None,
    to_time: Optional[str] = None,
    skip: int = 0,
    limit: int = 50,
    action: str = "",
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
        assignee_email=assignee_email,
        assigner_email=assigner_email,
        clearance_id=clearance_id,
        clearance_name=clearance_name,
        from_time=from_time,
        to_time=to_time,
        skip=skip,
        limit=limit,
        action=action,
    )

    return {"records": jsonable_encoder(assignment_history)}
