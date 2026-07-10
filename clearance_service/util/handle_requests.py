"""A module to handle requests to remote servers"""

from typing import Any, Callable, Optional

import requests
from requests import structures
from fastapi import status
from pydantic import BaseModel, Field

from clearance_service.util.settings import C9K_TIMEOUT


class RequestException(Exception):
    """
    Exception raised on a failed request, including exceptions
    from the requests module and 400+ status codes
    """

    def __init__(self, status_code: int, log_message: str):
        self.status_code = status_code
        self.message = log_message

    def __str__(self):
        return f"RequestException: {self.status_code} {self.message}"


class RequestData(BaseModel):
    """Kwargs used in requests get/post/etc methods"""

    url: str
    data: Optional[dict | str] = None
    headers: Optional[dict] = None
    request_json: Optional[dict] = Field(alias="json", default=None)


class RequestResponse:
    """Successful queries from handle_request return this type of object"""

    def __init__(
        self, status_code: int, json: Any, headers: structures.CaseInsensitiveDict
    ):
        self.status_code = status_code
        self.json = json
        self.headers = headers


def handle_request(
    requests_method: Callable, request_data: RequestData, timeout: float = C9K_TIMEOUT
) -> RequestResponse:
    """
    Process requests to remote servers
    Either return a response with the resulting status code, json data, and headers,
    or raise an exception with the appropriate status code

    Parameters:
        requests_method: A method from the requests module. get, post, etc
        request_data: Data used as kwargs for the requests_method
        timeout: Maximum time to wait for a server response, in seconds

    Returns: An object with status_code, json, and headers attributes
    """
    try:
        request_data_map = request_data.dict()
        request_data_map["json"] = request_data_map.pop("request_json")
        response = requests_method(**request_data_map, timeout=timeout)

    except requests.HTTPError:
        # An HTTP error occurred.
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            log_message="An error occurred with this request",
        )

    except requests.URLRequired:
        # A valid URL is required to make a request.
        raise RequestException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            log_message="A valid URL wasn't provided for this request",
        )

    except requests.TooManyRedirects:
        # Too many redirects.
        raise RequestException(
            status_code=status.HTTP_421_MISDIRECTED_REQUEST, log_message="Too many redirects"
        )

    except requests.ConnectTimeout:
        # The request timed out while trying to connect to the remote server.
        # Requests that produced this error are safe to retry.
        raise RequestException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            log_message=f"Unable to connect to remote server in {timeout} second(s)",
        )

    except requests.ReadTimeout:
        # The server did not send any data in the allotted amount of time.
        raise RequestException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            log_message=f"No response from remote server in {timeout} second(s)",
        )

    except requests.Timeout:
        # The request timed out.
        # Watching this error will catch both ConnectTimeout and ReadTimeout errors.
        raise RequestException(
            status_code=status.HTTP_408_REQUEST_TIMEOUT,
            log_message=f"Request took longer than {timeout} second(s)",
        )

    except requests.ConnectionError:
        # A Connection error occurred.
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            log_message="Could not connect to the remote host",
        )

    except requests.RequestException:
        # There was an ambiguous exception that occurred while handling your request.
        raise RequestException(
            status_code=status.HTTP_400_BAD_REQUEST,
            log_message="An exception occurred while handling this request",
        )

    if response.status_code in range(200, 300):
        return RequestResponse(
            status_code=response.status_code, json=response.json(), headers=response.headers
        )
    if response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR:
        raise RequestException(status_code=status.HTTP_400_BAD_REQUEST, log_message=response.text)
    raise RequestException(status_code=response.status_code, log_message=response.text)
