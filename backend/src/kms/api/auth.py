"""One shared password in front of the whole app, when APP_PASSWORD is set."""

import base64
import binascii
import secrets
from collections.abc import Awaitable, Callable

from fastapi import Request, Response
from fastapi.responses import JSONResponse

from kms.config import get_settings

# Left open so a deployment check needs no password; it shows only migration state.
OPEN_PATHS = {"/api/health"}


async def require_password(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """Let a request through only when it carries the app's password, by HTTP Basic Auth.

    Any username is accepted; only the password is checked. The browser shows its own login
    prompt on the 401 and then sends the password with every request to this site.

    Args:
        request: The incoming request.
        call_next: The rest of the app, called when the request may pass.

    Returns:
        The app's response; or a 401 with `{"detail": ...}` and a `WWW-Authenticate: Basic`
        challenge when the password is missing, malformed or wrong. Everything passes when
        APP_PASSWORD is empty, and the open paths always pass.
    """
    password = get_settings().app_password
    if not password or request.url.path in OPEN_PATHS:
        return await call_next(request)

    given = basic_auth_password(request.headers.get("authorization", ""))
    # compare_digest takes the same time however much of a guess is right, so the response
    # time gives nothing away.
    if given is not None and secrets.compare_digest(given.encode(), password.encode()):
        return await call_next(request)

    return JSONResponse(
        status_code=401,
        content={"detail": "Password required"},
        headers={"WWW-Authenticate": 'Basic realm="KMS", charset="UTF-8"'},
    )


def basic_auth_password(header: str) -> str | None:
    """Return the password from an `Authorization: Basic ...` header value.

    Args:
        header: The header's value, or "" when the request has none.

    Returns:
        The password, or None when the header is missing, not Basic, or not valid base64 of
        "username:password".
    """
    scheme, _, encoded = header.partition(" ")
    if scheme.lower() != "basic":
        return None
    try:
        decoded = base64.b64decode(encoded, validate=True).decode()
    except (binascii.Error, UnicodeDecodeError):
        return None
    _username, separator, password = decoded.partition(":")
    if not separator:
        return None
    return password
