from dataclasses import dataclass, field
from enum import Enum
from typing import Optional


class ExchangeRegistrar(Enum):
    # NOTE: for now, all durable topic exchanges
    INTERNAL_SERVICE_EVENT = "internal_service_events"
    EXTERNAL_SERVICE_EVENT = "external_service_events"


class EntityRegistrar(Enum):
    WORKER = "worker"
    GAME_SERVER_INSTANCE = "game_server_instance"


class MessageTypeRegistry(Enum):
    STATUS = "status"
    COMMAND = "command"


class TopicWildcard(Enum):
    ALL = "#"
    ANY = "*"


@dataclass
class RoutingKeyConfig:
    entity: EntityRegistrar
    identifier: str
    type: MessageTypeRegistry
    subtype: Optional[str] = None

    def build_key(
        self,
        entity_wildcard: Optional[TopicWildcard] = None,
        identifier_wildcard: Optional[TopicWildcard] = None,
        type_wildcard: Optional[TopicWildcard] = None,
        subtype_wildcard: Optional[TopicWildcard] = None,
    ) -> str:
        entity_str = entity_wildcard.value if entity_wildcard else self.entity.value
        identifier_str = (
            identifier_wildcard.value if identifier_wildcard else self.identifier
        )
        type_str = type_wildcard.value if type_wildcard else self.type.value

        if subtype_wildcard:
            subtype_str = f".{subtype_wildcard}"
        elif self.subtype:
            subtype_str = f".{self.subtype}"
        else:
            subtype_str = ""

        return f"{entity_str}.{identifier_str}.{type_str}{subtype_str}"


@dataclass
class QueueConfig:
    # TODO - more customization options for queue name
    name: str

    durable: bool
    exclusive: bool
    auto_delete: bool

    actual_queue_name: Optional[str] = field(default=None, init=False)

    def build_name(self):
        return self.name


@dataclass
class BindingConfig:
    exchange: ExchangeRegistrar
    routing_keys: list[RoutingKeyConfig]
