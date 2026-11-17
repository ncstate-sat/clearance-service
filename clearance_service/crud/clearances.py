"""Controller functions for clearance-related operations"""

from typing import Optional

from auth_checker import AuthChecker, TokenPayload
from clearance_service.models.clearance import Clearance
from clearance_service.util.authorization import get_authorization, user_is_admin
from clearance_service.util.authorization_roles import PERMISSIONS
from clearance_service.util.handle_requests import RequestException
from fastapi import APIRouter, Depends, Response
from fastapi.encoders import jsonable_encoder

router = APIRouter()


@router.get(
    "", tags=["Clearance"], dependencies=[Depends(AuthChecker(PERMISSIONS["CLEARANCES_READ"]))]
)
def get_clearances(
    response: Response,
    search: str = "",
    page_size: Optional[int] = None,
    page_num: Optional[int] = None,
    account: TokenPayload = Depends(get_authorization),
) -> dict:
    """
    Search clearances by name or search query and return details
    about those clearances

    Parameters:
        search: A query to search clearance names

    Returns: A list of Clearance objects matching the search
    """
    if user_is_admin(account.roles):
        try:
            clearances = Clearance.get(search, page_size=page_size, page_num=page_num)
        except RequestException as e:
            response.status_code = e.status_code
            return {"clearance_names": [], "detail": "Unable to get clearances"}
    else:
        email = account.email
        clearances = Clearance.get_allowed(email, search)

    return {"clearance_names": jsonable_encoder(clearances)}
