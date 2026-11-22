from typing import Annotated

from fastapi import Header, HTTPException, status

# Like Finance Profile and Financial IQ, this service does not validate tokens itself: the edge gateway does
# (JWT + "same user" check) and then writes the caller's id into X-User-Id, removing any value the client sent.
# Without the header the request did not come through the gateway, so it is refused.
USER_ID_HEADER = "X-User-Id"


def current_user_id(x_user_id: Annotated[str | None, Header(alias=USER_ID_HEADER)] = None) -> str:
    if not x_user_id or not x_user_id.strip():
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Missing X-User-Id (call through the gateway).")
    return x_user_id
