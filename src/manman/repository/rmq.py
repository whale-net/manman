import abc

from manman.models import Command


class MessageProvider(abc.ABCMeta):
    """
    Abstract base class for message providers.
    This class defines the interface for receiving messages.
    """

    @abc.abstractmethod
    @property
    def exchange(self) -> str:
        """
        Return the name of the exchange to use for message retrieval.
        """
        pass

    @abc.abstractmethod
    def get_messages(self) -> list[Command]:
        """
        Retrieve a list of messages from the message provider.
        This method should return a list of messages.
        """
        pass
