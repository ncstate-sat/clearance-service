"""Tests for the handle_request util function"""

import pytest
import requests

from clearance_service.util.handle_requests import (
    RequestData,
    RequestException,
    RequestResponse,
    handle_request,
)

# This is sourced from the requests test suite
# https://github.com/psf/requests/blob/30222533
# 4678490ec66b3614a9dddb8a02c5f4fe/tests/test_requests.py#LL57C1-L57C31
TARPIT = "http://10.255.255.1/"


@pytest.mark.parametrize("status_code", [400, 401, 403, 404, 408, 422])
def test_4xx_status_codes(status_code):
    """
    It should raise a RequestException with the same status code when it receives a 4xx status code
    from the remote server
    """
    with pytest.raises(RequestException) as excinfo:
        handle_request(
            requests.post, request_data=RequestData(url=f"https://mock.codes/{status_code}")
        )
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
        handle_request(requests.post, request_data=RequestData(url="https://mock.codes/500"))
    assert excinfo.value.status_code == 400


def test_200_status_code():
    """
    It should return a RequestResponse when it receives a 2xx status code from the remote server
    """
    response = handle_request(requests.post, request_data=RequestData(url="https://mock.codes/200"))
    assert isinstance(response, RequestResponse)
    assert response.status_code == 200
    assert "OK" in str(response.json)


def test_timeout():
    """It should raise a RequestException on timeout"""
    with pytest.raises(RequestException) as excinfo:
        handle_request(requests.post, request_data=RequestData(url=TARPIT), timeout=1)
    assert excinfo.value.status_code == 408
