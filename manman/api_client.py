import datetime
from pydantic import BaseModel, Field
from functools import cached_property
from jose import jwt
from typing import Optional, Any
import urllib.parse
import requests
import requests.auth
# import urllib


from manman.models import GameServerInstance, GameServerConfig, GameServer

# TODO LIST (TBD correct layer for each feature)
#   RETRY
#   STATUS_CODE HANDLING
#   COMMON CEREAL AND DECEREAL


class BaseUrlSession(requests.Session):
    def __init__(self, base_url: str = "") -> None:
        if len(base_url) == 0:
            # this is needed for mypy/lsp
            raise RuntimeError("tricked ya - it's needed")
        self._base_url = base_url
        super().__init__()

    def request(
        self, method: str | bytes, url: str | bytes, *args, **kwargs
    ) -> requests.Response:
        # joining will remove prefix on _base_url
        # full_url = urllib.parse.urljoin(self._base_url, url)

        append_to_url_base = kwargs.pop("append_to_url_base", True)
        if append_to_url_base:
            full_url = self._base_url + url
        else:
            full_url = url
        return super().request(method, full_url, *args, **kwargs)


class AccessToken(BaseModel):
    raw_token: str
    jwk: dict = Field(exclude=True)

    @cached_property
    def jwt(self):
        # TODO - verify audience
        decoded_jwt: dict[str, Any] = jwt.decode(
            self.raw_token, key=self.jwk, options={"verify_aud": False}
        )
        return decoded_jwt

    @cached_property
    def expires_at(self) -> datetime.datetime:
        return datetime.datetime.fromtimestamp(self.jwt["exp"])

    @cached_property
    def scopes(self) -> set[str]:
        scope_str = str(self.jwt.get("scope", ""))
        scopes = scope_str.split(" ")
        return set(scopes)

    def is_expired(self, expiry_threshold_seconds: int = 10) -> bool:
        expiration_delta = self.expires_at - datetime.datetime.now()
        return expiration_delta < datetime.timedelta(seconds=expiry_threshold_seconds)

    def is_valid(self) -> bool:
        # if jwt can be decoded, it is considered OK
        return len(self.jwt) > 0

    @classmethod
    def create_from_response(cls, response: requests.Response, jwk: dict):
        content = dict(response.json())
        return cls(raw_token=content.pop("access_token"), jwk=jwk)


class AccessTokenResponse(BaseModel):
    token_type: str
    access_token: AccessToken
    expires_in: int
    refresh_token: Optional[str]
    refresh_expires_in: Optional[int]

    @classmethod
    def create_from_response(cls, response: requests.Response, jwk: dict):
        access_token = AccessToken.create_from_response(response, jwk)
        content = dict(response.json())
        token_response = cls(
            token_type=content.pop("token_type"),
            access_token=access_token,
            expires_in=content.pop("expires_in"),
            refresh_token=content.get("refresh_token"),
            refresh_expires_in=content.get("refresh_expires_in"),
        )
        return token_response


class BearerAuth(requests.auth.AuthBase):
    def __init__(self, access_token: AccessToken):
        self.access_token = access_token

    def __call__(self, r):
        r.headers["authorization"] = "bearer " + self.access_token.raw_token
        return r


class APIClientBase:
    def __init__(self, base_url: str, api_prefix: str = "") -> None:
        # ironically, suffix the base_url with the prefix
        self._base_url = urllib.parse.urljoin(base_url, api_prefix)
        self._session = BaseUrlSession(self._base_url)


# TODO - is there a way to auto generate this? I feel I should be able to extend off openAPI spec
class WorkerAPIClient(APIClientBase):
    def __init__(self, base_url: str, api_prefix: str = "/workapi") -> None:
        super().__init__(base_url=base_url, api_prefix=api_prefix)

    def game_server(self, game_server_id: int) -> GameServer:
        response = self._session.get(f"/server/{game_server_id}")
        return GameServer.model_validate_json(response.content)

    def game_server_config(self, game_server_config_id: int) -> GameServerConfig:
        response = self._session.get(f"/server/config/{game_server_config_id}")
        return GameServerConfig.model_validate_json(response.content)

    def game_server_instance_create(
        self, config: GameServerConfig
    ) -> GameServerInstance:
        instance = GameServerInstance(
            game_server_config_id=config.game_server_config_id
        )
        # TODO - there is probably a way to centralize this without it being stupid
        response = self._session.post(
            "/server/instance/create", data=instance.model_dump_json()
        )
        return GameServerInstance.model_validate_json(response.content)

    def game_server_instance_shutdown(
        self, instance: GameServerInstance
    ) -> GameServerInstance:
        response = self._session.put(
            "/server/instance/shutdown", data=instance.model_dump_json()
        )
        return GameServerInstance.model_validate_json(response.content)


class AuthAPIClient(APIClientBase):
    # TODO - can api_prefix be removed from subclass if set up right in baseclass?
    def __init__(self, base_url: str, api_prefix: str = "") -> None:
        if len(api_prefix) > 0:
            raise RuntimeError("prefix not supported for auth client")

        discovery_response = requests.get(base_url)
        discovery_content = dict(discovery_response.json())
        self._public_key = discovery_content.pop("public_key")
        self._token_service = discovery_content.pop("token-service")
        # self._account_service = discovery_content.pop('account-service')

        # I really want to use this as a token service, so ignore base_url
        super().__init__(base_url=self._token_service, api_prefix=api_prefix)
        self._original_base_url = base_url

        # this may be keycloak specific endpoint but whatever
        certs_response = self._session.get("/certs")
        self._jwk = dict(certs_response.json())

    def get_access_token(
        self, client_id: str, client_secret: str
    ) -> AccessTokenResponse:
        response = self._session.post(
            "/token",
            auth=(client_id, client_secret),
            data={"grant_type": "client_credentials"},
        )
        if response.status_code != 200:
            raise RuntimeError(
                f"unable to auth {response.status_code} {response.content}"
            )
        return AccessTokenResponse.create_from_response(response, self._jwk)

    def validate_token(self, access_token: AccessToken, do_online_check: bool = True):
        # behavior of this is kind of whack since the online check will fail if the token is expired
        # whereas the offline doesn't
        # this behavior is probably fine though since online checks should be more rare
        if do_online_check:
            response = self._session.get(
                "/userinfo",
                auth=BearerAuth(access_token),
            )
            return response.status_code == 200
        else:
            return access_token.is_valid()
