import os
from fastapi import Header, HTTPException, Depends
import jwt


class AuthChecker:
    """
    AuthChecker objects ensure that the user is authorized to
    access a given route, using the jwt token in the request header.
    An HTTP Exception is raised if the user is not authorized.
    """

    def __init__(self, *required_authorizations):
        """
        :param tuple required_authorizations: Each item in the tuple
            is a string with the title of an authorization required
            by the function.
        """
        self.required_authorizations = required_authorizations

    def __call__(self, authorization=Header()):
        """
        When an AuthChecker object is called, get the 'Authorization'
        header from the request and check the user's permissions from the jwt.
        """
        self.check_authorization(authorization_header=authorization)

    def check_authorization(self, authorization_header):
        """
        Get the jwt from the header, decode to get the user's authorizations.
        Throw HTTP Exception if the user doesn't have all of the function's
        required authorizations.
        :param str authorization_header: the request's Authorization header.
            The header is an encoded JWT.
        """
        token = authorization_header.lstrip("Bearer").strip()
        if not token:
            raise HTTPException(401, detail="No token provided")
        try:
            secret = os.getenv("JWT_SECRET")
            if not secret:
                raise HTTPException(
                    400,
                    detail="No environment variable JWT_SECRET found"
                )
            payload = jwt.decode(
                token,
                secret,
                algorithms=["HS256"]
            )
        except jwt.exceptions.ExpiredSignatureError:
            raise HTTPException(400, detail="Token is expired")

        user_authorizations = payload.get("authorizations", {})
        if "root" in user_authorizations:
            # Then the user is authorized. Continue without any exceptions.
            return
        for required_auth in self.required_authorizations:
            # Throw a 403 if the authorization isn't there or is set to False:
            if user_authorizations.get(required_auth, False) is False:
                raise HTTPException(403, detail="User not authorized")


def require_auths(*required_authorizations):
    """
    Wrapper to simplify the syntax for using AuthChecker
    `require_auths("service-read")`
    is equivalent to
    `Depends(AuthChecker("service-read"))`

    :param required_authorizations: any number of authorizations
                                    required to access the endpoint
    """
    return Depends(AuthChecker(*required_authorizations))
