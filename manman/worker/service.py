import pika

from manman.worker.server import ServerID
from manman.util import NamedThreadPool

from manman.worker.server import Server, ServerType


class WorkerService:
    def __init__(
        self,
        root_install_dir: str,
        rabbitmq_host: str,
        rabbitmq_port: int,
        rabbitmq_username: str,
        rabbitmq_password: str,
    ):
        # TODO error checking
        self._root_install_dir = root_install_dir

        self._threadpool = NamedThreadPool()
        credentials = pika.credentials.PlainCredentials(
            username=rabbitmq_username, password=rabbitmq_password
        )
        self._rabbitmq_conn = pika.BlockingConnection(
            pika.ConnectionParameters(
                host=rabbitmq_host, port=rabbitmq_port, credentials=credentials
            )
        )

    def start_server(self, app_id: int, name: str):
        # TODO how to store servers?
        # list? is threadpool enough of a lifespan? is that dignified?
        # how to do communication to the servers?

        sid = ServerID(
            id="fish123", server_type=ServerType.STEAM, app_id=app_id, name=name
        )
        # TODO - retrieve executable from some mapping?
        server = Server(
            sid,
            self._root_install_dir,
            executable="game/bin/linuxsteamrt64/cs2",
        )
        print(server)
        # temp disable
        # server.run(
        #     args=["-dedicated", "-port", "27015", "+map", "de_ancient"],
        #     should_update=False,
        # )
