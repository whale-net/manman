import logging
from dataclasses import dataclass
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)


@dataclass
class ExchangeConfig:
    """Configuration for a single exchange and its routing keys."""
    name: str
    routing_keys: List[str]
    
    def __init__(self, name: str, routing_keys: Union[str, List[str]]):
        """
        Initialize ExchangeConfig with automatic string-to-list conversion.
        
        :param name: Exchange name
        :param routing_keys: Either a single routing key string or list of routing keys
        """
        self.name = name
        if isinstance(routing_keys, str):
            self.routing_keys = [routing_keys]
        else:
            self.routing_keys = list(routing_keys)  # Create a copy


@dataclass  
class ExchangesConfig:
    """Collection of exchange configurations."""
    exchanges: List[ExchangeConfig]
    
    def __init__(self, exchanges: List[ExchangeConfig]):
        """Initialize with a list of ExchangeConfig objects."""
        self.exchanges = exchanges
    
    @classmethod
    def from_legacy(cls, exchange: str, routing_key: str) -> 'ExchangesConfig':
        """
        Create from legacy single exchange format.
        
        :param exchange: Single exchange name
        :param routing_key: Single routing key
        :return: ExchangesConfig instance
        """
        return cls([ExchangeConfig(exchange, routing_key)])
    
    @classmethod
    def from_dict(cls, exchanges_config: Dict[str, Union[str, List[str]]]) -> 'ExchangesConfig':
        """
        Create from dictionary format.
        
        :param exchanges_config: Dictionary mapping exchange names to routing keys
        :return: ExchangesConfig instance
        """
        exchanges = []
        for name, routing_keys in exchanges_config.items():
            exchanges.append(ExchangeConfig(name, routing_keys))
        return cls(exchanges)
    
    def to_dict(self) -> Dict[str, List[str]]:
        """
        Convert to dictionary format for compatibility.
        
        :return: Dictionary mapping exchange names to routing key lists
        """
        return {exchange.name: exchange.routing_keys for exchange in self.exchanges}
    
    def get_exchange_names(self) -> List[str]:
        """Get list of all exchange names."""
        return [exchange.name for exchange in self.exchanges]


def add_routing_key_prefix(routing_key: str, prefix: Optional[str]) -> str:
    """
    Add a prefix to the routing key.

    :param routing_key: The original routing key.
    :param prefix: The prefix to add.
    :return: The modified routing key with the prefix added.
    """
    if prefix is None or len(prefix) == 0 or len(routing_key) == 0:
        return routing_key

    if not routing_key.startswith("."):
        routing_key = f"{prefix}.{routing_key}"
    else:
        routing_key = f"{prefix}{routing_key}"

    return routing_key


def add_routing_key_suffix(routing_key: str, suffix: Optional[str]) -> str:
    """
    Add a suffix to the routing key.

    :param routing_key: The original routing key.
    :param suffix: The suffix to add.
    :return: The modified routing key with the suffix added.
    """
    if suffix is None or len(suffix) == 0 or len(routing_key) == 0:
        return routing_key

    if not routing_key.endswith("."):
        routing_key += "."
    return f"{routing_key}{suffix}"


def declare_exchange(channel, exchange_name: str, exchange_type: str = "topic", 
                    durable: bool = True, auto_delete: bool = False) -> None:
    """
    Declare an exchange with common default settings.
    
    :param channel: The AMQP channel to use for declaration.
    :param exchange_name: Name of the exchange to declare.
    :param exchange_type: Type of exchange (default: "topic").
    :param durable: Whether the exchange should survive broker restarts (default: True).
    :param auto_delete: Whether the exchange should be deleted when not in use (default: False).
    """
    channel.exchange.declare(
        exchange=exchange_name,
        exchange_type=exchange_type,
        durable=durable,
        auto_delete=auto_delete,
    )
    logger.info("Exchange declared: %s", exchange_name)


def declare_queue(channel, queue_name: Optional[str] = None, 
                 auto_delete: bool = False, exclusive: bool = False) -> str:
    """
    Declare a queue with common settings.
    
    :param channel: The AMQP channel to use for declaration.
    :param queue_name: Name of the queue. If None, a random name will be generated.
    :param auto_delete: Whether the queue should be deleted when not in use.
    :param exclusive: Whether the queue should be exclusive to this connection.
    :return: The name of the declared queue.
    """
    result = channel.queue.declare(
        queue=queue_name or "",
        auto_delete=auto_delete,
        exclusive=exclusive,
    )
    if not result:
        logger.error("Unable to declare queue with name %s", queue_name)
        raise RuntimeError("Failed to create queue")
    
    declared_queue_name = result["queue"]
    logger.info("Queue declared: %s", declared_queue_name)
    return declared_queue_name


def normalize_exchanges_config(exchange: Optional[str] = None, 
                              routing_key_base: Optional[str] = None,
                              exchanges_config: Optional[Dict[str, Union[str, List[str]]]] = None) -> ExchangesConfig:
    """
    Normalize exchange configuration to a standard ExchangesConfig format.
    
    Converts both legacy single exchange format and new multiple exchanges format 
    to an ExchangesConfig object.
    
    :param exchange: Single exchange name (legacy parameter).
    :param routing_key_base: Single routing key (legacy parameter).
    :param exchanges_config: Dictionary mapping exchanges to routing keys.
    :return: Normalized ExchangesConfig object.
    """
    if exchanges_config:
        return ExchangesConfig.from_dict(exchanges_config)
    elif exchange and routing_key_base is not None:
        # Legacy single exchange support
        return ExchangesConfig.from_legacy(exchange, routing_key_base)
    else:
        raise ValueError(
            "Either 'exchange' and 'routing_key_base' or 'exchanges_config' must be provided"
        )


def generate_name_from_exchanges(exchanges_config: Union[ExchangesConfig, Dict[str, Union[str, List[str]]]], prefix: str = "") -> str:
    """
    Generate a descriptive name based on exchange names.
    
    :param exchanges_config: ExchangesConfig object or dictionary mapping exchange names to routing keys.
    :param prefix: Optional prefix for the generated name.
    :return: Generated name string.
    """
    if isinstance(exchanges_config, ExchangesConfig):
        exchange_names = "-".join(exchanges_config.get_exchange_names())
    else:
        exchange_names = "-".join(exchanges_config.keys())
    
    if prefix:
        return f"{prefix}-{exchange_names}"
    return exchange_names


def bind_queue_to_exchanges(channel, queue_name: str, 
                           exchanges_config: Union[ExchangesConfig, Dict[str, Union[str, List[str]]]]) -> None:
    """
    Bind a queue to multiple exchanges with their routing keys.
    
    :param channel: The AMQP channel to use for binding.
    :param queue_name: Name of the queue to bind.
    :param exchanges_config: ExchangesConfig object or dictionary mapping exchange names to routing key(s).
    """
    if isinstance(exchanges_config, ExchangesConfig):
        exchanges = exchanges_config.exchanges
    else:
        # Convert dict to ExchangesConfig for uniform processing
        exchanges = ExchangesConfig.from_dict(exchanges_config).exchanges
    
    for exchange in exchanges:
        for routing_key in exchange.routing_keys:
            channel.queue.bind(
                exchange=exchange.name,
                queue=queue_name,
                routing_key=routing_key,
            )
            logger.info(
                "Queue %s bound to exchange %s with routing key '%s'",
                queue_name,
                exchange.name,
                routing_key,
            )
