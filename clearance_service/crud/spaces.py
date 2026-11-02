"""Controller functions for space operations"""

from typing import Optional

from auth_checker import AuthChecker, TokenPayload
from clearance_service.models.personnel import Personnel
from clearance_service.models.space import Space
from clearance_service.util.authorization import get_authorization, user_is_admin
from clearance_service.util.authorization_roles import PERMISSIONS
from fastapi import APIRouter, Depends, Response, status
from pydantic import BaseModel

router = APIRouter()


class SpaceCreateBody(BaseModel):
    name: str
    door_ids: list[int]


@router.post(
    "/create",
    tags=["Space"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_SPACES_WRITE"]))],
)
def create_space(
    data: SpaceCreateBody,
    response: Response,
    account: TokenPayload = Depends(get_authorization),
) -> dict[str, str]:
    """Post a new space document to the `space` mongo collection"""
    if data.door_ids:
        available_doors = Personnel.get_doors_ungrouped(account.email)
        if unauthorized_door_ids := set(data.door_ids) - {door.id for door in available_doors}:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return {
                "detail": (
                    "Not authorized to assign door(s) "
                    f"{', '.join(str(door_id) for door_id in unauthorized_door_ids)}"
                )
            }
    space = Space(data.name, list(set(data.door_ids)), created_by=account.email)
    try:
        insert_result = space.create()
    except Exception as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {
            "detail": "Could not create new space",
            "error": str(e),
        }
    if insert_result.acknowledged:
        response.status_code = status.HTTP_201_CREATED
        return {
            "message": f"Created new space {data.name}",
            "space_id": str(insert_result.inserted_id),
        }
    response.status_code = status.HTTP_400_BAD_REQUEST
    return {"detail": "Could not create new space"}


@router.get(
    "/search",
    tags=["Space"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_SPACES_READ"]))],
)
def search_spaces(
    response: Response,
    account: TokenPayload = Depends(get_authorization),
    name: str = "",
    skip: int = 0,
    limit: int = 100,
) -> list | dict[str, str]:
    """Query mongo for spaces"""
    search_criteria = {"name": {"$regex": name}}
    if not user_is_admin(account.roles):
        search_criteria["created_by"] = account.email
    try:
        search_response = Space.search(search_criteria, skip, limit)
        for space in search_response:
            space["_id"] = str(space["_id"])
        return search_response
    except Exception as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {
            "detail": "Could not search spaces",
            "error": str(e),
        }


class SpaceUpdateBody(BaseModel):
    space_id: str
    new_name: Optional[str] = None
    new_door_ids: Optional[list[int]] = None


@router.put(
    "/update",
    tags=["Space"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_SPACES_WRITE"]))],
)
def update_space(
    data: SpaceUpdateBody,
    response: Response,
    account: TokenPayload = Depends(get_authorization),
) -> dict[str, str]:
    """Update an existing space document in mongo"""
    if data.new_name is None and data.new_door_ids is None:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail": "Must include either a new name or new list of doors to update"}
    if data.new_door_ids:
        available_doors = Personnel.get_doors_ungrouped(account.email)
        if unauthorized_door_ids := set(data.new_door_ids) - {door.id for door in available_doors}:
            response.status_code = status.HTTP_401_UNAUTHORIZED
            return {
                "detail": (
                    "Not authorized to assign door(s) "
                    f"{', '.join(str(door_id) for door_id in unauthorized_door_ids)}"
                )
            }
    try:
        update_response = Space.update(
            data.space_id,
            data.new_name,
            data.new_door_ids,
            account.email if not user_is_admin(account.roles) else None,
        )
    except Exception as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {
            "detail": "Not able to update space",
            "error": str(e),
        }
    if update_response.matched_count < 1:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail": "Could not find space"}
    return {"message": "Updated space"}


@router.delete(
    "/delete",
    tags=["Space"],
    dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCE_SPACES_WRITE"]))],
)
def delete_space(
    space_id: str,
    response: Response,
    account: TokenPayload = Depends(get_authorization),
):
    """Delete a space document from mongo"""
    try:
        delete_result = Space.delete(
            space_id, account.email if not user_is_admin(account.roles) else None
        )
    except Exception as e:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {
            "detail": "Not able to delete space",
            "error": str(e),
        }
    if delete_result.deleted_count < 1:
        response.status_code = status.HTTP_400_BAD_REQUEST
        return {"detail": "Not able to delete space"}
    return {"message": "Deleted space"}
