"""
Centralized logging configuration for ManMan application.

This module provides consistent logging setup across all services,
whether they run with uvicorn or standalone.
"""

import logging
import os
import sys
from typing import Optional

try:
    from opentelemetry._logs import set_logger_provider
    from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import (
        BatchLogRecordProcessor,
        # ConsoleLogExporter,
    )
    from opentelemetry.sdk.resources import Resource

    OTEL_AVAILABLE = True
except ImportError:
    OTEL_AVAILABLE = False

HAS_DONE_SETUP = False

logger = logging.getLogger(__name__)


def setup_logging(
    level: int = logging.INFO,
    service_name: Optional[str] = None,
    force_setup: bool = False,
    enable_otel: bool = False,
    enable_console: bool = True,
    otel_endpoint: Optional[str] = None,
) -> None:
    """
    Setup logging configuration for ManMan services with optional OTEL support.

    This function works with both standalone services and uvicorn-based services.
    For uvicorn, this should be called before uvicorn.run() and uvicorn will
    handle console logging while we add OTEL and configure log levels.

    Args:
        level: Logging level (default: INFO)
        service_name: Name of the service for log identification
        force_setup: Whether to force reconfiguration even if already setup
        enable_otel: Whether to enable OTEL logging (default: False)
        enable_console: Whether to enable console logging (default: True)
        otel_endpoint: OTEL collector endpoint (defaults to env var or localhost)
    """
    # Check if logging has already been configured
    root_logger = logging.getLogger()
    global HAS_DONE_SETUP
    if HAS_DONE_SETUP and not force_setup:
        # Logging already configured, just ensure our level is set
        logger.info(
            "Logging already configured, setting level to %s",
            logging.getLevelName(level),
        )
        root_logger.setLevel(level)
        # If OTEL is enabled and we are forcing setup, ensure the handler is present
        if enable_otel and OTEL_AVAILABLE and force_setup:
            # Remove existing OTEL handlers to avoid duplicates if any
            for handler in list(root_logger.handlers):  # Iterate over a copy
                if isinstance(handler, LoggingHandler):
                    root_logger.removeHandler(handler)
            _setup_otel_logging(service_name, otel_endpoint)  # Re-apply OTEL
        return
    else:
        HAS_DONE_SETUP = True

    # Setup OTEL logging if available and enabled
    if enable_otel and OTEL_AVAILABLE:
        _setup_otel_logging(service_name, otel_endpoint)

    # Setup console logging if enabled
    if enable_console:
        # Only setup console logging if we don't already have handlers
        # (uvicorn will add its own handlers)
        if not root_logger.handlers:
            logging.basicConfig(level=level)
            _setup_console_logging(service_name)

    # Configure root logger
    root_logger.setLevel(level)

    # Set specific loggers to appropriate levels
    # Reduce noise from common third-party libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("amqpstorm").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    # Ensure ManMan loggers are at the specified level
    logging.getLogger("manman").setLevel(level)
    logger.info(
        "Logging configured for service '%s' at level %s",
        service_name,
        logging.getLevelName(level),
    )


def _setup_otel_logging(
    service_name: Optional[str] = None, otel_endpoint: Optional[str] = None
) -> None:
    """
    Setup OTEL logging configuration.

    Args:
        service_name: Name of the service for identification
        otel_endpoint: OTEL collector endpoint
    """
    if not OTEL_AVAILABLE:
        return

    # Create OTEL logger provider with service identification
    logger_provider = LoggerProvider(
        resource=Resource.create(
            {
                "service.name": service_name or "manman",
                "service.instance.id": os.uname().nodename,
            }
        ),
    )
    set_logger_provider(logger_provider)

    # Setup OTLP exporter
    endpoint = (
        otel_endpoint
        or os.getenv("OTEL_EXPORTER_OTLP_LOGS_ENDPOINT")
        or "http://otel-collector.manman-dev.svc.cluster.local:4317"
    )

    otlp_exporter = OTLPLogExporter(
        endpoint=endpoint,
        insecure=True,
    )
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_exporter))

    # Add OTEL handler to root logger
    handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
    logging.getLogger().addHandler(handler)


def _setup_console_logging(service_name: Optional[str] = None) -> None:
    """
    Setup console logging configuration.

    Args:
        service_name: Name of the service for log identification
    """
    # Create formatter
    service_prefix = f"[{service_name}] " if service_name else ""
    formatter = logging.Formatter(
        f"%(asctime)s - {service_prefix}%(name)s - %(levelname)s - %(message)s"
    )

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Add to root logger
    logging.getLogger().addHandler(handler)
