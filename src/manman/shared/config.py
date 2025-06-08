"""
Shared configuration for ManMan API services.

This module provides centralized configuration for API services that can be
referenced by both the actual API implementations and OpenAPI generation.
"""

from dataclasses import dataclass
from typing import Dict, FrozenSet


@dataclass(frozen=True)
class APIConfig:
    """Configuration for a specific API service."""

    name: str
    title: str
    root_path: str


class APIServiceConfig:
    """Centralized configuration for ManMan API services."""

    # API service names
    EXPERIENCE_API = "experience-api"
    STATUS_API = "status-api"
    WORKER_DAL_API = "worker-dal-api"

    # All well-known API names for validation
    KNOWN_API_NAMES: FrozenSet[str] = frozenset([
        EXPERIENCE_API,
        STATUS_API,
        WORKER_DAL_API,
    ])

    # API configurations
    API_CONFIGS: Dict[str, APIConfig] = {
        EXPERIENCE_API: APIConfig(
            name=EXPERIENCE_API,
            title="ManMan Experience API",
            root_path="/experience",
        ),
        STATUS_API: APIConfig(
            name=STATUS_API,
            title="ManMan Status API",
            root_path="/status",
        ),
        WORKER_DAL_API: APIConfig(
            name=WORKER_DAL_API,
            title="ManMan Worker DAL API",
            root_path="/workerdal",
        ),
    }

    @classmethod
    def get_api_config(cls, api_name: str) -> APIConfig:
        """Get API configuration by name."""
        if api_name not in cls.API_CONFIGS:
            raise ValueError(
                f"Unknown API name: {api_name}. Valid options are: {', '.join(cls.KNOWN_API_NAMES)}"
            )
        return cls.API_CONFIGS[api_name]

    @classmethod
    def validate_api_name(cls, api_name: str) -> str:
        """Validate API name and return it if valid."""
        if api_name not in cls.KNOWN_API_NAMES:
            raise ValueError(
                f"Unknown API name: {api_name}. Valid options are: {', '.join(cls.KNOWN_API_NAMES)}"
            )
        return api_name