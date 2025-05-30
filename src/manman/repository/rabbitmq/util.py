import logging
from typing import Dict, List, Optional, Union

logger = logging.getLogger(__name__)


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
                              exchanges_config: Optional[Dict[str, Union[str, List[str]]]] = None) -> Dict[str, List[str]]:
    """
    Normalize exchange configuration to a standard format.
    
    Converts both legacy single exchange format and new multiple exchanges format 
    to a dictionary mapping exchange names to lists of routing keys.
    
    :param exchange: Single exchange name (legacy parameter).
    :param routing_key_base: Single routing key (legacy parameter).
    :param exchanges_config: Dictionary mapping exchanges to routing keys.
    :return: Normalized configuration with routing keys as lists.
    """
    if exchanges_config:
        config = exchanges_config
    elif exchange and routing_key_base is not None:
        # Legacy single exchange support
        config = {exchange: routing_key_base}
    else:
        raise ValueError(
            "Either 'exchange' and 'routing_key_base' or 'exchanges_config' must be provided"
        )
    
    # Normalize routing keys to lists
    normalized_config = {}
    for exchange_name, routing_keys in config.items():
        if isinstance(routing_keys, str):
            routing_keys = [routing_keys]
        normalized_config[exchange_name] = routing_keys
    
    return normalized_config


def generate_name_from_exchanges(exchanges_config: Dict[str, Union[str, List[str]]], prefix: str = "") -> str:
    """
    Generate a descriptive name based on exchange names.
    
    :param exchanges_config: Dictionary mapping exchange names to routing keys.
    :param prefix: Optional prefix for the generated name.
    :return: Generated name string.
    """
    exchange_names = "-".join(exchanges_config.keys())
    if prefix:
        return f"{prefix}-{exchange_names}"
    return exchange_names


def bind_queue_to_exchanges(channel, queue_name: str, 
                           exchanges_config: Dict[str, Union[str, List[str]]]) -> None:
    """
    Bind a queue to multiple exchanges with their routing keys.
    
    :param channel: The AMQP channel to use for binding.
    :param queue_name: Name of the queue to bind.
    :param exchanges_config: Dictionary mapping exchange names to routing key(s).
    """
    for exchange_name, routing_keys in exchanges_config.items():
        # Ensure routing_keys is always a list for iteration
        if isinstance(routing_keys, str):
            routing_keys = [routing_keys]

        for routing_key in routing_keys:
            channel.queue.bind(
                exchange=exchange_name,
                queue=queue_name,
                routing_key=routing_key,
            )
            logger.info(
                "Queue %s bound to exchange %s with routing key '%s'",
                queue_name,
                exchange_name,
                routing_key,
            )
