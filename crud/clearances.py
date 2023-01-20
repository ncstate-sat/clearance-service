"""
Controller functions for clearance-related operations.
"""

from typing import Union
from fastapi import APIRouter, Response, Depends, status
from util.auth_checker import AuthChecker
from middleware.get_authorization import get_authorization
from models.clearance import Clearance

router = APIRouter()


@router.get('', tags=['Clearance'], dependencies=[Depends(AuthChecker('clearance_read'))])
def get_clearances(response: Response,
                   search: Union[str, None] = None,
                   authorization: dict = Depends(get_authorization)) -> dict:
    """
    Searches clearances by name or search query and returns details
    about those clearances.

    Parameters:
        search: A query to search clearance names.
    """
    email = authorization.get('email', None)
    if email is None:
        raise RuntimeError('There must be an email address in this token.')

    if authorization.get('authorizations', {}).get('root', False):
        clearances = Clearance.get(search)
    else:
        clearances = Clearance.get(search)
        clearances = Clearance.filter_allowed(clearances, email=email)

    response.status_code = status.HTTP_200_OK
    return {
        'clearance_names': clearances
    }
