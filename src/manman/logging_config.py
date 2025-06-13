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
    from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
    from opentelemetry.sdk._logs.export import (
        BatchLogRecordProcessor,
        # ConsoleLogExporter,
    )
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor
    from opentelemetry.trace import set_tracer_provider

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

    # Setup OTEL logging and tracing if available and enabled
    if enable_otel and OTEL_AVAILABLE:
        _setup_otel_logging(service_name, otel_endpoint)
        _setup_otel_tracing(service_name, otel_endpoint)

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


def create_formatter(service_name: Optional[str] = None) -> logging.Formatter:
    """
    Create a standardized formatter for ManMan services.

    Args:
        service_name: Name of the service for log identification

    Returns:
        Configured logging formatter
    """
    service_prefix = f"[{service_name}] " if service_name else ""
    return logging.Formatter(
        f"%(asctime)s - {service_prefix}%(name)s - %(levelname)s - %(message)s"
    )


def setup_server_logging(service_name: Optional[str] = None) -> None:
    """
    Setup logging for web servers (uvicorn/gunicorn) that preserves existing handlers.

    This function configures server-specific loggers without clobbering
    the root logger configuration, allowing OTEL and other handlers to coexist.
    Uses Python objects directly instead of dictionary-based configuration
    for better maintainability and error detection.

    Args:
        service_name: Name of the service for log identification
    """
    formatter = create_formatter(service_name)

    # Create a console handler for server logs
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)

    # Configure server-specific loggers
    server_loggers = [
        "uvicorn",
        "uvicorn.error",
        "uvicorn.access",
        "gunicorn",
        "gunicorn.access",
        "gunicorn.error",
    ]

    for logger_name in server_loggers:
        logger = logging.getLogger(logger_name)
        # Clear any existing handlers to avoid duplicates
        logger.handlers.clear()
        logger.addHandler(console_handler)
        logger.setLevel(logging.INFO)
        logger.propagate = False  # Don't propagate to root to avoid duplicate logs


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
    )

    otlp_exporter = OTLPLogExporter(
        endpoint=endpoint,
        insecure=True,
    )
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_exporter))

    # Add OTEL handler to root logger
    handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
    logging.getLogger().addHandler(handler)


def _setup_otel_tracing(
    service_name: Optional[str] = None, otel_endpoint: Optional[str] = None
) -> None:
    """
    Setup OTEL tracing configuration.

    Args:
        service_name: Name of the service for identification
        otel_endpoint: OTEL collector endpoint
    """
    if not OTEL_AVAILABLE:
        return

    # Create OTEL tracer provider with service identification
    resource = Resource.create(
        {
            "service.name": service_name or "manman",
            "service.instance.id": os.uname().nodename,
        }
    )
    tracer_provider = TracerProvider(resource=resource)
    set_tracer_provider(tracer_provider)

    # Setup OTLP span exporter
    # Use traces endpoint if specified, otherwise use the base OTLP endpoint
    traces_endpoint = (
        otel_endpoint
        or os.getenv("OTEL_EXPORTER_OTLP_TRACES_ENDPOINT")
        or os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT")
    )

    otlp_span_exporter = OTLPSpanExporter(
        endpoint=traces_endpoint,
        insecure=True,
    )
    tracer_provider.add_span_processor(BatchSpanProcessor(otlp_span_exporter))


def _setup_console_logging(service_name: Optional[str] = None) -> None:
    """
    Setup console logging configuration.

    Args:
        service_name: Name of the service for log identification
    """
    # Use the standardized formatter
    formatter = create_formatter(service_name)

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Add to root logger
    logging.getLogger().addHandler(handler)


def get_gunicorn_config(
    service_name: str,
    port: int = 8000,
    workers: int = 1,
    worker_class: str = "uvicorn.workers.UvicornWorker",
    preload_app: bool = True,
    enable_otel: bool = False,
) -> dict:
    """
    Get Gunicorn configuration for ManMan services.

    Note: Logging configuration is handled separately in app factory functions
    to ensure proper initialization order using Python objects instead of
    dictionary-based configuration.

    Args:
        service_name: Name of the service for identification
        port: Port to bind to
        workers: Number of worker processes
        worker_class: Gunicorn worker class to use
        preload_app: Whether to preload the application before forking workers
        enable_otel: Whether OTEL logging is enabled (unused but kept for compatibility)

    Returns:
        Configuration dict for Gunicorn
    """
    # Base configuration - same for all services
    config = {
        "bind": f"0.0.0.0:{port}",
        "workers": workers,
        "worker_class": worker_class,
        "worker_connections": 1000,
        "max_requests": 1000,
        "max_requests_jitter": 100,
        "preload_app": preload_app,
        "keepalive": 2,
        "timeout": 30,
        "graceful_timeout": 30,
        # Logging format and output
        "access_log_format": f'[{service_name}] %(h)s "%(r)s" %(s)s %(b)s "%(f)s" "%(a)s" %(D)s',
        "accesslog": "-",  # Log to stdout
        "errorlog": "-",  # Log to stderr
        "loglevel": "info",
        "capture_output": True,
        "enable_stdio_inheritance": True,
    }

    # Note: Logging configuration should be handled in the app factory functions
    # rather than here, to ensure proper initialization order
    return config
