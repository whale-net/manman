"""
CLI for generating OpenAPI specs without environment dependencies.
"""

import json
import logging
from pathlib import Path
from typing import Dict, Tuple

import typer
from fastapi import FastAPI
from typing_extensions import Annotated

from manman.host.api.shared import add_health_check
from manman.logging_config import setup_logging

app = typer.Typer()
logger = logging.getLogger(__name__)

# API configurations matching those in main.py
API_CONFIGS: Dict[str, Tuple[str, str]] = {
    "experience-api": ("ManMan Experience API", "/experience"),
    "status-api": ("ManMan Status API", "/status"),
    "worker-dal-api": ("ManMan Worker DAL API", "/workerdal"),
}

# Known API names for validation
KNOWN_API_NAMES = frozenset(API_CONFIGS.keys())


def _generate_openapi_spec(fastapi_app: FastAPI, service_name: str) -> None:
    """Generate and save OpenAPI spec for a FastAPI app."""
    output_path = Path("./openapi-specs")
    output_path.mkdir(exist_ok=True)

    spec = fastapi_app.openapi()
    spec_file = output_path / f"{service_name}.json"
    with open(spec_file, "w") as f:
        json.dump(spec, f, indent=2)

    logger.info(f"OpenAPI spec saved to: {spec_file}")
    typer.echo(f"OpenAPI spec saved to: {spec_file}")


@app.callback(invoke_without_command=True)
def main(
    api_name: Annotated[
        str,
        typer.Argument(
            help=f"Name of the API to generate OpenAPI spec for. Options: {', '.join(KNOWN_API_NAMES)}"
        ),
    ],
):
    """Generate OpenAPI specification for a specific API without requiring environment setup."""
    # Setup logging
    setup_logging(service_name="openapi-generator")
    logger.info(f"Generating OpenAPI spec for {api_name}...")

    # Validate API name
    if api_name not in KNOWN_API_NAMES:
        raise typer.BadParameter(
            f"Unknown API name: {api_name}. Valid options are: {', '.join(KNOWN_API_NAMES)}"
        )

    # Get API configuration
    title, root_path = API_CONFIGS[api_name]

    # Build FastAPI app based on API
    fastapi_app = FastAPI(title=title, root_path=root_path)
    
    if api_name == "experience-api":
        from manman.host.api.experience import router as experience_router

        fastapi_app.include_router(experience_router)
        add_health_check(fastapi_app)

    elif api_name == "status-api":
        from manman.host.api.status import router as status_router

        fastapi_app.include_router(status_router)
        add_health_check(fastapi_app)

    elif api_name == "worker-dal-api":
        from manman.host.api.worker_dal import server_router, worker_router

        fastapi_app.include_router(server_router)
        fastapi_app.include_router(worker_router)
        add_health_check(fastapi_app)

    # Generate and save the spec
    _generate_openapi_spec(fastapi_app, api_name)
    logger.info(f"OpenAPI spec generation completed for {api_name}")
