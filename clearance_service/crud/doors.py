"""Controller functions for door operations"""


from auth_checker import AuthChecker, TokenPayload
from clearance_service.models import acs
from clearance_service.models.personnel import Personnel
from clearance_service.util.authorization import get_authorization
from clearance_service.util.authorization_roles import PERMISSIONS
from clearance_service.util.handle_requests import RequestException
from fastapi import APIRouter, Depends, Response, status

router = APIRouter()


@router.post(
    "/lock",
    tags=["Door"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_DOORS_WRITE"]))],
)
def lock_door(
    door_id: int,
    response: Response,
    account: TokenPayload = Depends(get_authorization),
) -> dict[str, str]:
    """
    Lock a door indefinitely. The user must have permission to assign the door.

    Parameters:
        door_id: The ACS ID of the door to be locked

    Returns: dict with one key: "message" for success and "detail" for failure
    """
    if door_id in {door.id for door in Personnel.get_doors_ungrouped(account.email)}:
        try:
            acs_response = acs.action.door.lock(door_id)
            return {"message": acs_response.json}
        except RequestException as e:
            response.status_code = e.status_code
            return {"detail": f"Unable to lock door {door_id}: {e.message}"}
    response.status_code = status.HTTP_401_UNAUTHORIZED
    return {"detail": f"Not authorized to lock door {door_id}"}


@router.post(
    "/unlock",
    tags=["Door"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_DOORS_WRITE"]))],
)
def unlock_door(
    door_id: int,
    response: Response,
    account: TokenPayload = Depends(get_authorization),
) -> dict[str, str]:
    """
    Unock a door indefinitely. The user must have permission to assign the door.

    Parameters:
        door_id: The ACS ID of the door to be unlocked

    Returns: dict with one key: "message" for success and "detail" for failure
    """
    if door_id in {door.id for door in Personnel.get_doors_ungrouped(account.email)}:
        try:
            acs_response = acs.action.door.unlock(door_id)
            return {"message": acs_response.json}
        except RequestException as e:
            response.status_code = e.status_code
            return {"detail": f"Unable to unlock door {door_id}: {e.message}"}
    response.status_code = status.HTTP_401_UNAUTHORIZED
    return {"detail": f"Not authorized to unlock door {door_id}"}
