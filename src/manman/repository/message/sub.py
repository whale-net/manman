import logging

from manman.models import Command
from manman.repository.message.abstract_interface import MessageSubscriberInterface

logger = logging.getLogger(__name__)


class CommandSubService:
    """
    Service for subscribing to messages
    """

    def __init__(self, subscriber: MessageSubscriberInterface) -> None:
        self._subscriber = subscriber
        logger.info(
            "MessageSubService initialized with subscriber %s", self._subscriber
        )

    def get_commands(self) -> list[Command]:
        """
        Consume a command message from RabbitMQ.

        :return: The consumed command.
        """

        commands = []
        for message in self._subscriber.consume():
            command = Command.model_validate_json(message)
            commands.append(command)
        return commands
