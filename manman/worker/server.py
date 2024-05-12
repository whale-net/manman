import logging
import os
import threading
from typing import Self

from manman.api_client import WorkerAPIClient

# import sqlalchemy
# from sqlalchemy.orm import Session
# from pydantic import BaseModel
from manman.models import GameServerConfig, GameServerInstance, ServerType
from manman.processbuilder import ProcessBuilder, ProcessBuilderStatus
from manman.util import get_rabbitmq_connection
from manman.worker.steamcmd import SteamCMD

logger = logging.getLogger(__name__)


# TODO logging
class Server:
    RMQ_EXCHANGE = "server"

    def __init__(
        self,
        wapi: WorkerAPIClient,
        root_install_directory: str,
        config: GameServerConfig,
    ) -> None:
        self._wapi = wapi
        self._config = config

        self._instance = self._wapi.game_server_instance_create(config)
        self._game_server = self._wapi.game_server(self._config.game_server_id)
        logger.info("starting instance %s", self._instance.model_dump_json())

        self._rmq_channel = get_rabbitmq_connection().channel()
        self._rmq_channel.exchange_declare(Server.RMQ_EXCHANGE, exchange_type="direct")
        result = self._rmq_channel.queue_declare("", exclusive=True)
        self._rmq_queue_name = result.method.queue
        self._rmq_channel.queue_bind(
            queue=self._rmq_queue_name,
            exchange=Server.RMQ_EXCHANGE,
            routing_key=str(self._instance.game_server_instance_id),
        )

        self._root_install_directory = root_install_directory
        self._server_directory = os.path.join(
            self._root_install_directory,
            # game_server is unique on server_type_appid
            ServerType(self._game_server.server_type).name.lower(),
            str(self._game_server.app_id),
            # and then config is unique on game_server_id, name
            self._config.name,
        )

        executable_path = os.path.join(self._server_directory, self._config.executable)
        pb = ProcessBuilder(executable=executable_path)
        for arg in self._config.args:
            pb.add_parameter(arg)
        self._pb = pb

    @property
    def instance(self) -> GameServerInstance:
        return self._instance

    # def add_stdin(self, input: str):
    #     # TODO check if pb is running
    #     self._pb.stdin_queue.put(input)

    # def stop(self):
    #     status = self._pb.status
    #     if status not in (ProcessBuilderStatus.INIT, ProcessBuilderStatus.RUNNING):
    #         logger.info("invalid stop received, current_status = %s", status)
    #         return

    def _process_queue(self):
        logger.info("starting to read queue")
        self._rmq_channel.basic_consume(
            self._rmq_queue_name,
            on_message_callback=self._process_message,
            auto_ack=True,
        )
        self._rmq_channel.start_consuming()

    def _process_message(self, ch, method, properties, body):
        logger.info("body=%s", body)
        logger.warning("killing server")
        self._pb.kill()
        return

    def shutdown(self):
        # TODO kill
        if self._instance.end_date is None:
            logger.info("shutting down")
            self.instance = self._wapi.game_server_instance_shutdown(self._instance)
            self._t.join()

    def run(self, should_update: bool = True) -> Self:
        logger.info("instance %s starting", self._instance.game_server_instance_id)

        # TODO - temp workaround
        self._t = threading.Thread(target=self._process_queue)
        self._t.start()

        if should_update:
            steam = SteamCMD(self._server_directory)
            steam.install(app_id=self._game_server.app_id)
        self._pb.execute()
        status = self._pb.status
        while status != ProcessBuilderStatus.STOPPED:
            self._pb.read_output()
            status = self._pb.status

        # do it one more time to clean up anything leftover
        self._pb.read_output()
        logger.info("instance %s ended", self._instance.game_server_instance_id)
        self.shutdown()

        return self
