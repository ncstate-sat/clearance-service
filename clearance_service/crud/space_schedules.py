"""Controller functions for space-schedule operations"""

from datetime import datetime
from typing import Literal, Optional

from auth_checker.models.models import Account
from auth_checker.models.models import TokenAuthorizer as AuthChecker
from bson import ObjectId
from clearance_service.models.space_schedule import SpaceSchedule
from clearance_service.util.authorization import get_authorization, user_is_admin
from clearance_service.util.authorization_roles import READ_ROLES, READ_WRITE_ROLES
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

router = APIRouter()


class SpaceScheduleCreateBody(BaseModel):
    space_id: str
    action_time: datetime
    action_type: Literal["lock", "unlock"]
    series_name: Optional[str] = ""


@router.post(
    "/create",
    tags=["SpaceSchedule"],
    dependencies=[Depends(AuthChecker(READ_WRITE_ROLES))],
)
def create_space_schedule(
    data: SpaceScheduleCreateBody,
    response: Response,
    account: Account = Depends(get_authorization),
) -> dict[str, str]:
    """Post a new space_schedule document to the `space_schedule` mongo collection"""
    space_schedule = SpaceSchedule(
        space_id=data.space_id,
        action_time=data.action_time,
        action_type=data.action_type,
        series_name=data.series_name,
        created_by=account.email,
    )
    try:
        insert_result = space_schedule.create()
    except Exception as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {
            "detail": "Could not create new space schedule",
            "error": str(e),
        }
    if insert_result.acknowledged:
        response.status_code = status.HTTP_201_CREATED
        return {
            "message": f"Created schedule to {data.action_type} space",
            "space_id": str(insert_result.inserted_id),
        }
    response.status_code = status.HTTP_400_BAD_REQUEST
    return {"detail": "Could not create new space schedule"}


@router.get("/search", tags=["SpaceSchedule"], dependencies=[Depends(AuthChecker(READ_ROLES))])
def search_space_schedules(
    response: Response,
    space_id: Optional[str] = None,
    action_type: Optional[str] = None,
    series_name: Optional[str] = None,
    account: Account = Depends(get_authorization),
    skip: int = 0,
    limit: int = 100,
) -> list | dict[str, str]:
    """Query mongo for space schedules"""
    search_criteria = (
        ({"space_id": ObjectId(space_id)} if space_id else {})
        | ({"action_type": action_type} if action_type else {})
        | ({"series_name": series_name} if series_name else {})
    )
    if not user_is_admin(account.roles):
        search_criteria["created_by"] = account.email
    try:
        search_response = SpaceSchedule.search(search_criteria, skip, limit)
        for schedule in search_response:
            schedule["_id"] = str(schedule["_id"])
            schedule["space_id"] = str(schedule["space_id"])
        return search_response
    except Exception as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {
            "detail": "Could not search space schedules",
            "error": str(e),
        }


class SpaceScheduleUpdateBody(BaseModel):
    schedule_id: str
    space_id: Optional[str] = None
    action_time: Optional[datetime] = None


@router.put(
    "/update",
    tags=["SpaceSchedule"],
    dependencies=[Depends(AuthChecker(READ_WRITE_ROLES))],
)
def update_space_schedule(
    data: SpaceScheduleUpdateBody,
    response: Response,
    account: Account = Depends(get_authorization),
) -> dict[str, str]:
    """Update an existing space_schedule document in mongo with a new space ID and/or action time"""
    if data.space_id is None and data.action_time is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail": "Must include either a new space or new action time to update"}
    try:
        update_response = SpaceSchedule.update(
            data.schedule_id,
            data.space_id,
            data.action_time,
            account.email if not user_is_admin(account.roles) else None,
        )
    except Exception as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {
            "detail": "Not able to update space schedule",
            "error": str(e),
        }
    if update_response.matched_count < 1:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail": "Could not find space schedule"}
    return {"message": "Updated space schedule"}


@router.delete(
    "/delete",
    tags=["SpaceSchedule"],
    dependencies=[Depends(AuthChecker(READ_WRITE_ROLES))],
)
def delete_space_schedule(
    schedule_id: str,
    response: Response,
    account: Account = Depends(get_authorization),
) -> dict[str, str]:
    """Delete a space_schedule document from mongo"""
    try:
        delete_result = SpaceSchedule.delete(
            schedule_id, account.email if not user_is_admin(account.roles) else None
        )
    except Exception as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {
            "detail": "Not able to delete space schedule",
            "error": str(e),
        }
    if delete_result.deleted_count < 1:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail": "Not able to delete space schedule"}
    return {"message": "Deleted space schedule"}
