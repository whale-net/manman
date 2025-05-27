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
    if root_logger.handlers and not force_setup:
        # Logging already configured, just ensure our level is set
        root_logger.setLevel(level)
        return

    # Clear any existing handlers if we're forcing setup
    if force_setup:
        root_logger.handlers.clear()

    # Setup OTEL logging if available and enabled
    if enable_otel and OTEL_AVAILABLE:
        _setup_otel_logging(service_name, otel_endpoint)

    # Setup console logging if enabled
    if enable_console:
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


def get_uvicorn_log_config(service_name: Optional[str] = None) -> dict:
    """
    Get uvicorn-compatible log configuration that plays nicely with our setup.

    Args:
        service_name: Name of the service for log identification

    Returns:
        Log configuration dict for uvicorn
    """
    service_prefix = f"[{service_name}] " if service_name else ""

    return {
        "version": 1,
        "disable_existing_loggers": False,
        "formatters": {
            "default": {
                "format": f"%(asctime)s - {service_prefix}%(name)s - %(levelname)s - %(message)s",
            },
            "access": {
                "format": f"%(asctime)s - {service_prefix}uvicorn.access - %(levelname)s - %(message)s",
            },
        },
        "handlers": {
            "default": {
                "formatter": "default",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
            "access": {
                "formatter": "access",
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
            },
        },
        "loggers": {
            "uvicorn": {"handlers": ["default"], "level": "INFO", "propagate": False},
            "uvicorn.error": {
                "handlers": ["default"],
                "level": "INFO",
                "propagate": False,
            },
            "uvicorn.access": {
                "handlers": ["access"],
                "level": "INFO",
                "propagate": False,
            },
        },
        "root": {
            "level": "INFO",
            "handlers": ["default"],
        },
    }


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
