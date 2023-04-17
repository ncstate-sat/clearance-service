"""Controller functions for personnel operations"""

from typing import Optional
from fastapi import APIRouter, Response, status, Depends
import requests
from auth_checker import AuthChecker
from models.personnel import Personnel

router = APIRouter()


@router.get("", tags=["Personnel"],
            dependencies=[Depends(AuthChecker("personnel_read"))])
def search_personnel(response: Response,
                     search: Optional[str] = None) -> dict:
    """
    Search any and all personnel

    Parameters:
        search: The search query for personnel
    """
    try:
        personnel = Personnel.search(search)
    except requests.ConnectTimeout:
        print(f"CCure timeout: Could not find personnel with search {search}")
        response.status_code = status.HTTP_408_REQUEST_TIMEOUT
        return {"personnel": []}

    results = []
    for person in personnel:
        results.append(person.__dict__)

    response.status_code = status.HTTP_200_OK
    return {"personnel": results}
