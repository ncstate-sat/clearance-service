"""
Module representing authorization middleware.
"""

import os
import jwt
from fastapi import Header


def get_authorization(authorization: str = Header(default=None)):
    """
    Extracts authorization details out of the token.
    """
    token = authorization.split(' ')[1]
    payload = jwt.decode(token, os.getenv('JWT_SECRET'), ['HS256'])
    return payload