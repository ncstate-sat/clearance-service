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
        campus_id = authorization.get("campus_id", None)
        if campus_id is None:
            response.status_code = 400
            raise RuntimeError("There must be a campus ID in this token.")
        clearances = Clearance.get_allowed(campus_id, search)

    else:  # if the user is root
        try:
            clearances = Clearance.get(search)
        except requests.ConnectTimeout:
            response.status_code = 408
            print(("CCure timeout. "
                   f"Could not get clearances with search {search}"))
            return {"clearance_names": []}

    response.status_code = status.HTTP_200_OK
    return {"clearance_names": clearances}
