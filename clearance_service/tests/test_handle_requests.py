"""Tests for the handle_request util function"""

import json

import pytest
import requests

from clearance_service.util.handle_requests import (
    RequestData,
    RequestException,
    RequestResponse,
    handle_request,
)

REQUEST_DATA = RequestData(url="https://api.example.com/resource")


def respond_with(status_code: int, body: dict | None = None):
    """Build a stand-in for a requests method that returns a response with the given status."""
    response = requests.Response()
    response.status_code = status_code
    response._content = json.dumps(body or {}).encode()

    def fake_requests_method(**_):
        return response

    return fake_requests_method


def raise_error(error: Exception):
    """Build a stand-in for a requests method that raises the given error."""

    def fake_requests_method(**_):
        raise error

    return fake_requests_method


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 408, 422])
def test_4xx_status_codes(status_code):
    """
    It should raise a RequestException with the same status code when it receives a 4xx status code
    from the remote server
    """
    with pytest.raises(RequestException) as excinfo:
        handle_request(respond_with(status_code), request_data=REQUEST_DATA)
    assert excinfo.value.status_code == status_code


def test_400_status_code():
    """
    It should raise a RequestException with 400 status code for invalid URL
    from the remote server
    """
    with pytest.raises(RequestException) as excinfo:
        handle_request(
            requests.post, request_data=RequestData(url="'https://api.example.com/invalid-url'")
        )
    assert excinfo.value.status_code == 400


def test_500_status_code():
    """
    It should raise a RequestException with a 400 status code when it receives a 500 status code
    from the remote server
    """
    with pytest.raises(RequestException) as excinfo:
        handle_request(respond_with(500), request_data=REQUEST_DATA)
    assert excinfo.value.status_code == 400


def test_200_status_code():
    """
    It should return a RequestResponse when it receives a 2xx status code from the remote server
    """
    response = handle_request(respond_with(200, {"description": "OK"}), request_data=REQUEST_DATA)
    assert isinstance(response, RequestResponse)
    assert response.status_code == 200
    assert "OK" in str(response.json)


def test_timeout():
    """It should raise a RequestException on timeout"""
    with pytest.raises(RequestException) as excinfo:
        handle_request(raise_error(requests.ConnectTimeout()), request_data=REQUEST_DATA)
    assert excinfo.value.status_code == 408
