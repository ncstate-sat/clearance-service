"""
Module representing authorization middleware override for testing.
"""
from auth_checker.models.models import Account
from fastapi import Header


def override_get_authorization_admin():
    """Mock get_authorization for an admin user"""
    return Account(
        {
            "name": "Ryan Semmler",
            "email": "test_user@test.edu",
            "client_email": None,
            "roles": ["dev"],
        }
    )


def override_get_authorization_liaison(authorization: str = Header(default=None)):
    """Mock get_authorization for a liaison user"""
    account = Account(
        {
            "name": "Ryan Semmler",
            "email": "test_user@test.edu",
            "client_email": "",
            "roles": ["clearance:access"],
        }
    )
    match authorization:
        case "Bearer token1":
            account.email = "person1@email.com"
        case "Bearer token2":
            account.email = "person2@email.com"
        case "Bearer token3":
            account.email = "person3@email.com"
        case "Bearer token4":
            account.email = "person4@email.com"
        case "Bearer token5":
            account.email = "person5@email.com"
    return account
