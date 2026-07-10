"""Controller functions for clearance assignment operations."""

from datetime import datetime
from typing import Literal, Optional

from auth_checker.models.models import Account
from auth_checker.models.models import TokenAuthorizer as AuthChecker
from clearance_service.models import acs, filters
from clearance_service.models.clearance import Clearance
from clearance_service.models.personnel import Personnel
from clearance_service.models.scheduled_action import ScheduledAction
from clearance_service.util.authorization import get_authorization, user_is_admin
from clearance_service.util.authorization_roles import READ_ROLES, READ_WRITE_ROLES
from clearance_service.util.handle_requests import RequestException
from clearance_service.util.settings import C9K_CLEARANCE_LIMIT
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

router = APIRouter()


class ClearanceAssignRequestBody(BaseModel):
    """Model for the body of a request to assign clearances"""

    assignee_emails: list[str]
    clearance_ids: list[int]
    start_time: Optional[datetime] = None
    end_time: Optional[datetime] = None


class ClearanceRevokeRequestBody(BaseModel):
    """Model for the body of a request to revoke clearances"""

    assignee_emails: list[str]
    clearance_ids: list[int]
    action_time: Optional[datetime] = None


@router.post(
    "/assign",
    tags=["Assignments"],
    dependencies=[Depends(AuthChecker(READ_WRITE_ROLES))],
)
def assign_clearances(
    response: Response,
    body: ClearanceAssignRequestBody,
    account: Account = Depends(get_authorization),
) -> dict:
    """
    Assign one or more clearances to one or more people

    Parameters
        body: data on the assignees and clearances to be assigned
    """
    if len(body.clearance_ids) == 0:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"record": {}, "detail": "At least one clearance is required to assign a clearance."}
    if len(body.assignee_emails) == 0:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"record": {}, "detail": "At least one assignee is required to assign a clearance."}

    assigner_email = account.get_email
    if assigner_email is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail": "There must be an email address in this token."}

    if user_is_admin(account.roles):
        ids_to_assign = body.clearance_ids
    else:
        allowed_clearances = Clearance.get_allowed(assigner_email)
        allowed_ids = [clearance.id for clearance in allowed_clearances]
        ids_to_assign = [_id for _id in body.clearance_ids if _id in allowed_ids]
        if len(ids_to_assign) != len(body.clearance_ids):
            response.status_code = status.HTTP_403_FORBIDDEN
            return {"detail": "Not authorized to assign all selected clearances"}

    configs = []
    configs.extend(
        [
            ScheduledAction.ActionConfig(
                assigner_email=assigner_email,
                assigner_name=account.name if account.name else assigner_email,
                assignee_email=assignee_email,
                clearance_id=clearance_id,
                action="assign",
                action_time=body.start_time,
            )
            for assignee_email in body.assignee_emails
            for clearance_id in ids_to_assign
        ]
    )
    if body.end_time:
        configs.extend(
            [
                ScheduledAction.ActionConfig(
                    assigner_email=assigner_email,
                    assigner_name=account.name if account.name else assigner_email,
                    assignee_email=assignee_email,
                    clearance_id=clearance_id,
                    action="revoke",
                    action_time=body.end_time,
                )
                for assignee_email in body.assignee_emails
                for clearance_id in ids_to_assign
            ]
        )

    try:
        assignment_results = ScheduledAction.process(configs=configs)
        return assignment_results
    except KeyError:
        print(
            f"{assigner_email} could not assign all of the following clearances "
            f"because at least one does not exist: {', '.join(map(str, body.clearance_ids))}"
        )
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"changes": 0, "detail": "At least one of these clearances does not exist."}
    except RequestException as e:
        response.status_code = e.status_code
        if e.status_code == status.HTTP_403_FORBIDDEN:
            return {
                "detail": (
                    f"Individuals cannot have more than {C9K_CLEARANCE_LIMIT} clearances assigned"
                ),
            }
        return {"detail": f"Could not assign clearances: ({e})"}
    except RuntimeError as e:
        response.status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        error_message = "Could not assign permissions"
        if str(e) == "At least one clearance ID is required.":
            response.status_code = status.HTTP_400_BAD_REQUEST
            error_message = "At least one clearance is required to assign a clearance."
        return {"record": {}, "detail": error_message}


@router.post(
    "/revoke",
    tags=["Assignments"],
    dependencies=[Depends(AuthChecker(READ_WRITE_ROLES))],
)
def revoke_clearances(
    response: Response,
    body: ClearanceRevokeRequestBody,
    account: Account = Depends(get_authorization),
) -> dict:
    """
    Revoke one or more clearances to one or more people

    Parameters
        body: data on the assignees and clearances to be revoked
    """
    if len(body.clearance_ids) == 0:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"record": {}, "detail": "At least one clearance to be revoked is required."}
    if len(body.assignee_emails) == 0:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"record": {}, "detail": "At least one assignee is required to revoke a clearance."}

    assigner_email = account.get_email
    if assigner_email is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail": "There must be an email address in this token."}

    if user_is_admin(account.roles):
        revoke_ids = body.clearance_ids
    else:
        allowed_clearances = Clearance.get_allowed(assigner_email)
        allowed_ids = [clearance.id for clearance in allowed_clearances]
        revoke_ids = [_id for _id in body.clearance_ids if _id in allowed_ids]
        if len(revoke_ids) != len(body.clearance_ids):
            response.status_code = status.HTTP_403_FORBIDDEN
            return {"changes": 0, "detail": "Not authorized to revoke all selected clearances"}

    try:
        results = ScheduledAction.process(
            configs=[
                ScheduledAction.ActionConfig(
                    assigner_email=assigner_email,
                    assigner_name=account.name if account.name else assigner_email,
                    assignee_email=assignee_email,
                    clearance_id=clearance_id,
                    action="revoke",
                    action_time=body.action_time,
                )
                for assignee_email in body.assignee_emails
                for clearance_id in revoke_ids
            ]
        )
        return results
    except RequestException as e:
        response.status_code = e.status_code
        return {"changes": 0, "detail": "Could not revoke clearance"}


class GetScheduledActionsBody(BaseModel):
    assigner_email: Optional[str] = None
    assignee_email: Optional[str] = None
    from_time: Optional[datetime] = None
    clearance_id: Optional[int] = None
    to_time: Optional[datetime] = None
    action_type: Optional[Literal["assign", "revoke"]] = None
    status: Optional[
        list[Literal["pending", "succeeded", "failed", "cancelled", "already_completed"]]
    ] = [
        "pending",
        "succeeded",
        "failed",
        "cancelled",
        "already_completed",
    ]
    skip: int = 0
    limit: int = 50


@router.post(
    "/scheduled-actions",
    tags=["Assignments"],
    dependencies=[Depends(AuthChecker(READ_ROLES))],
)
def get_scheduled_actions(
    response: Response,
    body: GetScheduledActionsBody,
    account: Account = Depends(get_authorization),
):
    if not body.assigner_email and not user_is_admin(account.roles):
        user = Personnel.find_one(account.email, [])
        if user:
            body.assigner_email = user.email
        if not body.assigner_email:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {"detail": "An assigner_email is required"}
    scheduled_actions = ScheduledAction.get(**body.model_dump())

    if user_is_admin(account.roles):
        for action in scheduled_actions["actions"]:
            action["can_cancel"] = True
    else:
        assigner_email = account.get_email
        allowed_clearances = Clearance.get_allowed(assigner_email)
        allowed_ids = {clearance.id for clearance in allowed_clearances}

        for action in scheduled_actions["actions"]:
            action["can_cancel"] = action["clearance_id"] in allowed_ids

    response.status_code = status.HTTP_200_OK
    return {"actions": scheduled_actions["actions"], "count": scheduled_actions["count"]}


class BulkScheduleConfig(BaseModel):
    """For bulk scheduling clearance assignment and revocation actions"""

    assignee_email: str
    clearance_id: int
    action_type: str
    action_time: datetime


@router.post(
    "/bulk-schedule-actions",
    tags=["Assignments"],
    dependencies=[Depends(AuthChecker(READ_WRITE_ROLES))],
)
def bulk_schedule_actions(
    response: Response,
    body: list[BulkScheduleConfig],
    account: Account = Depends(get_authorization),
):
    """Add actions to the scheduled_action db collection"""
    assigner_email = account.get_email
    personnel_filter = filters.PersonnelFilter(
        lookups={"EmailAddress": filters.NFUZZ},
        display_properties=["Name"],
    )
    assigner_results = acs.personnel.search([assigner_email], personnel_filter)
    if assigner_results:
        assigner_name = assigner_results[0].get("Name", assigner_email)
    else:
        assigner_name = assigner_email
    action_configs = [
        ScheduledAction.ActionConfig(
            assigner_email=assigner_email,
            assigner_name=assigner_name,
            assignee_email=action.assignee_email,
            clearance_id=action.clearance_id,
            action=action.action_type,
            action_time=action.action_time,
        )
        for action in body
    ]
    try:
        ScheduledAction.bulk_schedule_actions(action_configs)
    except Exception as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"message": f"Could not schedule actions: {e}"}
    return action_configs


class CancelFutureActionBody(BaseModel):
    """
    For cancelling scheduled actions
    action_ids: stringified mongo Object IDs
    """

    action_ids: list[str]


@router.post(
    "/cancel-scheduled-actions",
    tags=["Assignments"],
    dependencies=[Depends(AuthChecker(READ_WRITE_ROLES))],
)
def cancel_scheduled_actions(
    response: Response, body: CancelFutureActionBody, account: Account = Depends(get_authorization)
):
    assigner_email = account.get_email
    if assigner_email is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail": "There must be an email address in this token."}

    action_ids = body.action_ids
    future_actions = ScheduledAction.get(assignment_ids=action_ids, status=["pending"], limit=1000)[
        "actions"
    ]

    assignment_clearance_ids = {action["clearance_id"] for action in future_actions}

    if not user_is_admin(account.roles):
        allowed_clearances = Clearance.get_allowed(
            assigner_email
        )  # TODO we don't need clearance names here, why bother getting them
        allowed_ids = {clearance.id for clearance in allowed_clearances}
        if assignment_clearance_ids - allowed_ids:
            response.status_code = status.HTTP_403_FORBIDDEN
            return {"detail": "Not authorized to cancel these actions."}

    try:
        cancellation_count = ScheduledAction.cancel_scheduled_actions(action_ids)
        return {"cancellations": cancellation_count}
    except RequestException as e:
        response.status_code = e.status_code
        return {"detail": e.message}


@router.get(
    "/{email}",
    tags=["Assignments"],
    dependencies=[Depends(AuthChecker(READ_ROLES))],
)
def get_assignments(
    response: Response,
    email: str,
    get_doors: Optional[bool] = False,
    account: Account = Depends(get_authorization),
) -> dict:
    """
    Return all active clearance assignments for an individual given their email address.

    Parameters:
        email: The email address of the person for which to query clearance assignments
        get_doors: Boolean value, whether the doors of each clearance should be returned

    Returns:
        list of the individual's assignments, each with name, id, and
            whether the user is authorized to revoke it
    """
    try:
        assignments = ScheduledAction.get_clearances_by_assignee(email)
    except RequestException as e:
        response.status_code = e.status_code
        error_message = "Could not get user's clearance assignments"
        return {"assignments": [], "detail": error_message}

    if not assignments:
        return {"assignments": []}

    all_assignments = []
    if user_is_admin(account.roles):
        for assignment in assignments:
            all_assignments.append(
                {
                    "id": assignment.id,
                    "name": assignment.name,
                    "can_revoke": True,
                }
            )
    else:
        assigner_email = account.get_email
        allowed_clearances = Clearance.get_allowed(assigner_email)
        allowed_ids = {clearance.id for clearance in allowed_clearances}

        for assignment in assignments:
            all_assignments.append(
                {
                    "id": assignment.id,
                    "name": assignment.name,
                    "can_revoke": assignment.id in allowed_ids,
                }
            )

    if get_doors:
        clearance_ids = [assignment["id"] for assignment in all_assignments]
        doors = Clearance.get_doors_by_clearance_id(clearance_ids)
        for assignment in all_assignments:
            assignment["doors"] = doors.get(assignment["id"], {})

    return {"assignments": all_assignments}
