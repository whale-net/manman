"""
Centralized logging configuration for ManMan application.

This module provides consistent logging setup across all services,
whether they run with uvicorn or standalone.
"""

import logging
import sys
from typing import Optional


def setup_logging(
    level: int = logging.INFO,
    service_name: Optional[str] = None,
    force_setup: bool = False,
) -> None:
    """
    Setup logging configuration for ManMan services.

    Args:
        level: Logging level (default: INFO)
        service_name: Name of the service for log identification
        force_setup: Whether to force reconfiguration even if already setup
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

    # Create formatter
    service_prefix = f"[{service_name}] " if service_name else ""
    formatter = logging.Formatter(
        f"%(asctime)s - {service_prefix}%(name)s - %(levelname)s - %(message)s"
    )

    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    # Configure root logger
    root_logger.setLevel(level)
    root_logger.addHandler(handler)

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
