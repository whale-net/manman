from typing import Annotated

from fastapi import Depends, Header, HTTPException

from manman.api_client import AccessToken
from manman.util import get_auth_api_client, get_rabbitmq_connection


# using builtin fastapi classes is not helpful because my token provider endpoint is elsewhere
# and not handled by fastapi whatsoever
# there doesn't seem to be a way to handle that in a reasonable way
async def get_access_token(authorization: Annotated[str, Header()]) -> AccessToken:
    # print(authorization)
    # return

    if not (authorization.startswith("bearer ") or authorization.startswith("bearer ")):
        raise RuntimeError("bearer token not found")

    api_client = get_auth_api_client()
    token = api_client.create_token_from_str(authorization[7:])
    if not token.is_valid():
        raise RuntimeError("token invalid")
    if token.is_expired():
        raise RuntimeError("token expired")
    return token


async def has_basic_worker_authz(
    token: Annotated[AccessToken, Depends(get_access_token)],
):
    if "manman-worker" not in token.roles:
        raise HTTPException(status_code=401, detail="access token missing proper role")


async def inject_rmq_channel():
    channel = get_rabbitmq_connection().channel()
    yield channel
    channel.close()
