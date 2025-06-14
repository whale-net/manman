"""
Log Subscriber Service for Server Instance Log Message Pass-Through.

This service consumes server instance messages containing log messages and 
re-emits them in a way that preserves the original service identity.
"""

import logging
import time
from datetime import datetime, timedelta

from amqpstorm import Connection

from manman.models import LogMessage
from manman.repository.message.sub import LogMessageSubService
from manman.repository.rabbitmq.config import (
    BindingConfig,
    EntityRegistry,
    ExchangeRegistry,
    MessageTypeRegistry,
    QueueConfig,
    RoutingKeyConfig,
    TopicWildcard,
)
from manman.repository.rabbitmq.subscriber import RabbitSubscriber

logger = logging.getLogger(__name__)


class LogSubscriberService:
    """
    Service that consumes log messages and re-emits them preserving original service identity.
    
    This acts as a transparent pass-through for log data, enabling log collection 
    through existing infrastructure and potentially exposing logs to web interfaces.
    """
    
    def __init__(self, rabbitmq_connection: Connection):
        """
        Initialize the log subscriber service.
        
        :param rabbitmq_connection: Connection to RabbitMQ
        """
        self._rabbitmq_connection = rabbitmq_connection
        self._running = False
        self._log_subscriber = self._build_log_subscriber()
        
        logger.info("LogSubscriberService initialized")
    
    def _build_log_subscriber(self) -> LogMessageSubService:
        """Build the log message subscriber."""
        # Subscribe to all log messages from all entities
        routing_keys = [
            RoutingKeyConfig(
                entity=TopicWildcard.ANY,
                identifier=TopicWildcard.ANY,
                type=MessageTypeRegistry.LOG,
            )
        ]
        
        binding_config = BindingConfig(
            exchange=ExchangeRegistry.INTERNAL_SERVICE_EVENT,
            routing_keys=routing_keys,
        )
        
        queue_config = QueueConfig(
            name="log-subscriber-queue",
            durable=True,
            exclusive=False,
            auto_delete=False,
        )
        
        rabbit_subscriber = RabbitSubscriber(
            self._rabbitmq_connection, 
            binding_config, 
            queue_config
        )
        
        return LogMessageSubService(rabbit_subscriber)
    
    def _process_log_messages(self):
        """Process available log messages and re-emit them."""
        try:
            log_messages = self._log_subscriber.get_log_messages()
            
            for log_message in log_messages:
                # Re-emit the log message preserving original service identity
                # For now, we'll just log it with the original service metadata
                # Future implementations could route to different outputs or web interfaces
                self._re_emit_log_message(log_message)
                
        except Exception as e:
            logger.exception("Error processing log messages: %s", e)
    
    def _re_emit_log_message(self, log_message: LogMessage):
        """
        Re-emit a log message preserving the original service identity.
        
        This method processes the log message and emits it in a format that 
        appears to come from the original service (not the subscriber).
        
        :param log_message: The log message to re-emit
        """
        try:
            # Create a logger name that preserves the original service identity
            original_service_name = f"{log_message.entity_type.value}.{log_message.identifier}"
            original_logger = logging.getLogger(f"manman.services.{original_service_name}")
            
            # Determine log level for re-emission
            log_level = getattr(logging, log_message.log_level.upper(), logging.INFO)
            
            # Create log message with timestamp and source information
            formatted_message = f"[{log_message.timestamp.isoformat()}] [{log_message.source}] {log_message.message}"
            
            # Re-emit the log with the original service logger
            original_logger.log(log_level, formatted_message)
            
        except Exception as e:
            logger.warning("Failed to re-emit log message: %s", e)
    
    def run(self):
        """
        Run the log subscriber service.
        
        This continuously processes log messages in a loop.
        """
        logger.info("Starting LogSubscriberService")
        self._running = True
        
        try:
            while self._running:
                self._process_log_messages()
                
                # Small delay to avoid busy waiting
                time.sleep(0.1)
                
        except KeyboardInterrupt:
            logger.info("LogSubscriberService interrupted by user")
        except Exception as e:
            logger.exception("Error in LogSubscriberService main loop: %s", e)
        finally:
            self._running = False
            logger.info("LogSubscriberService stopped")
    
    def stop(self):
        """Stop the log subscriber service."""
        logger.info("Stopping LogSubscriberService")
        self._running = False