"""Tests for the personnel endpoints"""

from fastapi.testclient import TestClient
from auth_checker import AuthChecker
from util.authorization import get_authorization
from tests.override_get_authorization import override_get_authorization
from models.personnel import Personnel
from main import app


app.dependency_overrides[get_authorization] = override_get_authorization
client = TestClient(app)


def mock_check_authorization(*_, **__):
    """"Mock AuthChecker response"""
    return None


def test_search_personnel(monkeypatch):
    """It should be able to search for personnel."""
    def mock_search(*_):
        return [
            Personnel(
                first_name="John",
                middle_name="Tyler",
                last_name="Champion",
                email="jtchampi@test.biz",
                campus_id="001132808"
            ),
            Personnel(
                first_name="Lisa",
                middle_name=None,
                last_name="Moose",
                email="lmoose@test.co.uk",
                campus_id="001132809"
            ),
        ]
    monkeypatch.setattr(Personnel, "search", mock_search)
    monkeypatch.setattr(AuthChecker, "check_authorization",
                        mock_check_authorization)

    response = client.get("/personnel?search=marina",
                          headers={"Authorization": "Bearer token"})
    assert response.status_code == 200
    json = response.json()
    assert "personnel" in json
    assert isinstance(json["personnel"], list)
