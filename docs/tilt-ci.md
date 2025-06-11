# Tilt CI Integration Testing

This repository includes a comprehensive integration testing workflow using Tilt CI that deploys the complete application stack to a Kubernetes cluster in GitHub Actions.

## Overview

The Tilt CI workflow (`.github/workflows/tilt-ci.yml`) provides end-to-end integration testing by:

1. **Setting up a local Kubernetes cluster** using kind
2. **Installing Tilt CLI** in the GitHub Actions runner
3. **Deploying the full application stack** including:
   - PostgreSQL database
   - RabbitMQ message broker
   - NGINX ingress controller
   - OpenTelemetry collector
   - All manman APIs (experience, worker-dal, status)
4. **Validating deployment health** and service readiness
5. **Collecting logs and diagnostics** on failure

## Configuration

The CI environment is configured via:
- **`.env.ci`**: CI-specific environment variables
- **`Tiltfile`**: Existing Tilt configuration (works in CI mode)
- **`charts/manman-host/`**: Helm chart for the application

## Running Locally

To validate the Tilt CI setup locally:

```bash
./scripts/validate-tilt-ci.sh
```

To run Tilt locally for development:

```bash
tilt up
```

## Troubleshooting

If the Tilt CI workflow fails:

1. Check the workflow logs in GitHub Actions
2. Review the uploaded Tilt snapshot artifact
3. Examine the cluster logs artifact for pod and event details
4. Ensure all required environment variables are set in `.env.ci`

The workflow includes comprehensive error collection and debugging information to help diagnose issues.
