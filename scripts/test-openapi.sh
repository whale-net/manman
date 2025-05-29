#!/bin/bash
# Simple smoke test for OpenAPI generation
# This script can be run locally to test that the OpenAPI generation is working

set -e

echo "🧪 Running OpenAPI generation smoke test..."

# Clean up any existing specs
rm -rf openapi-specs

# Test each API
apis=("experience-api" "status-api" "worker-dal-api")

for api in "${apis[@]}"; do
    echo "🔄 Testing $api..."
    
    # Generate the spec
    openapi "$api"
    
    # Check that the file was created
    spec_file="openapi-specs/${api}.json"
    if [[ ! -f "$spec_file" ]]; then
        echo "❌ Spec file not found: $spec_file"
        exit 1
    fi
    
    # Basic JSON validation
    if ! jq empty "$spec_file" >/dev/null 2>&1; then
        echo "❌ Invalid JSON in $spec_file"
        exit 1
    fi
    
    # Check for required OpenAPI fields
    if ! jq -e '.openapi' "$spec_file" >/dev/null; then
        echo "❌ Missing 'openapi' field in $spec_file"
        exit 1
    fi
    
    if ! jq -e '.info' "$spec_file" >/dev/null; then
        echo "❌ Missing 'info' field in $spec_file"
        exit 1
    fi
    
    title=$(jq -r '.info.title' "$spec_file")
    version=$(jq -r '.info.version' "$spec_file")
    
    echo "✅ $api: $title v$version"
done

echo "🎉 All OpenAPI generation tests passed!"
echo ""
echo "Generated files:"
ls -la openapi-specs/