from typing import Optional
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
    def __init__(self, base_url: Optional[str] = None) -> None:
        if base_url is None:
            # this is needed for mypy/lsp
            raise RuntimeError("tricked ya - it's needed")
        self._base_url = base_url
        super().__init__()

    def request(
        self, method: str | bytes, url: str | bytes, *args, **kwargs
    ) -> requests.Response:
        # joining will remove prefix on _base_url
        # full_url = urllib.parse.urljoin(self._base_url, url)
        full_url = self._base_url + url
        return super().request(method, full_url, *args, **kwargs)


class APIClientBase:
    def __init__(self, base_url: str, _api_prefix: Optional[str] = None) -> None:
        # ironically, suffix the base_url with the prefix
        self._base_url = urllib.parse.urljoin(base_url, _api_prefix)
        self._session = BaseUrlSession(self._base_url)


# TODO - is there a way to auto generate this? I feel I should be able to extend openAPI
class WorkerAPI(APIClientBase):
    def __init__(self, base_url: str, _api_prefix: Optional[str] = "/workapi") -> None:
        super().__init__(base_url=base_url, _api_prefix=_api_prefix)
        print(self._session._base_url)

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
