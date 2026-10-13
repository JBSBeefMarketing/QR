"""Password protection for /admin.

One shared username and password, supplied by the host as an environment
variable. Browsers prompt for it natively, so there is no login page to build
and nothing stored in the database.

This is deliberately modest. It is the right amount of security for an
internal tool that edits marketing copy, and it has one job: stop the open
internet from editing JBS product pages.

The public side - the resolver and the product pages - is never protected.
Those exist to be read by anyone who scans a package.
"""

from __future__ import annotations

import secrets

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBasic, HTTPBasicCredentials

from . import config

# auto_error=False so a request with no credentials reaches our handler
# instead of being rejected by the dependency. That lets the local, no-password
# case through without a browser prompt.
security = HTTPBasic(realm="JBS Digital Link admin", auto_error=False)

UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Incorrect username or password",
    headers={"WWW-Authenticate": 'Basic realm="JBS Digital Link admin"'},
)

UNCONFIGURED_MESSAGE = (
    "The admin area is locked because no password is set. "
    "Set the JBS_DL_ADMIN_PASSWORD environment variable on the host and "
    "restart, then reload this page."
)


def require_admin(
    credentials: HTTPBasicCredentials | None = Depends(security),
) -> str:
    """Check the shared credentials.

    With no password configured we fail closed on a real domain and stay open
    locally. Running on a laptop should not need a password; running on the
    public internet without one would be worse than useless.
    """
    if not config.ADMIN_PASSWORD:
        if config.IS_PROVISIONAL:
            return "local"
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=UNCONFIGURED_MESSAGE,
        )

    if credentials is None:
        raise UNAUTHORIZED

    # compare_digest avoids leaking the password through response timing.
    user_ok = secrets.compare_digest(credentials.username, config.ADMIN_USER)
    password_ok = secrets.compare_digest(credentials.password, config.ADMIN_PASSWORD)

    if not (user_ok and password_ok):
        raise UNAUTHORIZED
    return credentials.username
