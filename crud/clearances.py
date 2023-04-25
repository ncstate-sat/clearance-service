"""Controller functions for clearance-related operations"""

from typing import Optional
from fastapi import APIRouter, Response, Depends, status
import requests
from auth_checker import AuthChecker
from util.authorization import get_authorization, user_is_admin
from models.clearance import Clearance

router = APIRouter()


@router.get("", tags=["Clearance"],
            dependencies=[Depends(AuthChecker("clearance_read"))])
def get_clearances(response: Response,
                   search: Optional[str] = None,
                   jwt_payload: dict = Depends(get_authorization)) -> dict:
    """
    Search clearances by name or search query and returns details
    about those clearances

    Parameters:
        search: A query to search clearance names

    Returns: A list of Clearance objects matching the search
    """
    if user_is_admin(jwt_payload):
        try:
            clearances = Clearance.get(search)
        except requests.ConnectTimeout:
            response.status_code = status.HTTP_408_REQUEST_TIMEOUT
            print(("CCure timeout. "
                   f"Could not get clearances with search {search}"))
            return {"clearance_names": []}
    else:
        email = jwt_payload.get("email", None)
        if email is None:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {"detail": "There must be an email address in this token."}
        clearances = Clearance.get_allowed(email, search)

    response.status_code = status.HTTP_200_OK
    return {"clearance_names": clearances}
