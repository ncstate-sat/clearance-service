"""Module representing authorization middleware"""
import os

import jwt
from auth_checker.models.models import Account
from fastapi import Header
from sat.logs import SATLogger

from clearance_service.util.authorization_roles import ADMIN_ROLES

logger = SATLogger(__name__)


def get_authorization(authorization: str = Header(default=None)) -> Account:
    """Middleware to extract authorization details out of the token"""
    token = authorization.split(" ")[1]
    payload = jwt.decode(
        token, os.getenv("JWT_SECRET"), ["HS256"], options={"verify_signature": False}
    )
    payload_account = payload.get("account", payload)
    account = Account(payload_account)
    logger.debug(f"Authorization payload: {account.render()}")
    return account


def user_is_admin(roles: list) -> bool:
    """Whether the authenticated user has an admin role"""
    return any(user_role in ADMIN_ROLES for user_role in roles)
