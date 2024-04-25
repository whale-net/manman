from manman.util import NamedThreadPool

from manman.worker.server import Server, ServerID, ServerType


class WorkerService:
    def __init__(self, root_install_dir: str):
        # TODO error checking
        self._root_install_dir = root_install_dir

        self._threadpool = NamedThreadPool()

    def start_server(self, app_id: int, name: str):
        # TODO how to store servers?
        # list? is threadpool enough of a lifespan? is that dignified?
        # how to do communication to the servers?

        sid = ServerID(ServerType.STEAM, app_id, name)
        server = Server(sid, self._root_install_dir, executable="ls")
        server.run()
