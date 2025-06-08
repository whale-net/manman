"""
CLI for generating OpenAPI specs without environment dependencies.
"""

import json
import logging
from pathlib import Path

import typer
from fastapi import FastAPI
from typing_extensions import Annotated

from manman.host.api.shared import add_health_check
from manman.logging_config import setup_logging
from manman.shared.config import APIServiceConfig

app = typer.Typer()
logger = logging.getLogger(__name__)


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
            help=f"Name of the API to generate OpenAPI spec for. Options: {', '.join(APIServiceConfig.KNOWN_API_NAMES)}"
        ),
    ],
):
    """Generate OpenAPI specification for a specific API without requiring environment setup."""
    # Setup logging
    setup_logging(service_name="openapi-generator")
    logger.info(f"Generating OpenAPI spec for {api_name}...")

    # Validate API name
    try:
        APIServiceConfig.validate_api_name(api_name)
    except ValueError as e:
        raise typer.BadParameter(str(e))

    # Get API configuration
    api_config = APIServiceConfig.get_api_config(api_name)

    # Build FastAPI app based on API
    fastapi_app = FastAPI(title=api_config.title, root_path=api_config.root_path)
    
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
