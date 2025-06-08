import logging

from manman.models import InternalStatusInfo
from manman.repository.message.abstract_interface import MessagePublisherInterface

logger = logging.getLogger(__name__)


class StatusInfoPubService:
    def __init__(self, publisher: MessagePublisherInterface) -> None:
        self._publisher = publisher
        logger.info(
            "StatusInfoPubService initialized with publisher %s", self._publisher
        )

    def publish_status(self, internal_status: InternalStatusInfo) -> None:
        """
        Publish a status message to RabbitMQ.

        :param status_info: The status information to publish.
        """
        message = internal_status.model_dump_json()
        self._publisher.publish(message)
