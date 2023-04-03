"""Controller functions for clearance-related operations"""

from typing import Optional
from fastapi import APIRouter, Response, Depends, status
import requests
from auth_checker import AuthChecker
from middleware.get_authorization import get_authorization
from models.clearance import Clearance

router = APIRouter()


@router.get("", tags=["Clearance"],
            dependencies=[Depends(AuthChecker("clearance_read"))])
def get_clearances(response: Response,
                   search: Optional[str] = None,
                   authorization: dict = Depends(get_authorization)) -> dict:
    """
    Search clearances by name or search query and returns details
    about those clearances

    Parameters:
        search: A query to search clearance names

    Returns: A list of Clearance objects matching the search
    """
    if authorization.get("authorizations", {}).get("root", False) is False:
        email = authorization.get("email", None)
        if email is None:
            response.status_code = status.HTTP_400_BAD_REQUEST
            return {"detail": "There must be an email address in this token."}
        clearances = Clearance.get_allowed(email, search)

    else:  # if the user is root
        try:
            clearances = Clearance.get(search)
        except requests.ConnectTimeout:
            response.status_code = status.HTTP_408_REQUEST_TIMEOUT
            print(("CCure timeout. "
                   f"Could not get clearances with search {search}"))
            return {"clearance_names": []}

    response.status_code = status.HTTP_200_OK
    return {"clearance_names": clearances}
