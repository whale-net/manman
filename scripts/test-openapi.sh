#!/bin/bash

# Test script for OpenAPI generation
# This script validates that OpenAPI specs can be generated correctly for all APIs

set -e

echo "🧪 Testing OpenAPI generation for all APIs..."

# Check if we're in the right directory
if [ ! -f "pyproject.toml" ]; then
    echo "❌ Error: This script must be run from the project root directory"
    exit 1
fi

# Create output directory
OUTPUT_DIR="openapi-specs"
mkdir -p "$OUTPUT_DIR"

# List of APIs to test
APIS=("experience-api" "status-api" "worker-dal-api")

# Colors for output
GREEN='\033[0;32m'
RED='\033[0;31m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo "📦 Installing dependencies..."
if command -v uv &> /dev/null; then
    uv sync --dev
else
    echo "❌ Error: uv is not installed. Please install uv first:"
    echo "  pip install uv"
    exit 1
fi

echo "🔄 Generating OpenAPI specifications..."

for api in "${APIS[@]}"; do
    echo -e "\n${YELLOW}Generating $api...${NC}"
    
    if uv run openapi "$api"; then
        echo -e "${GREEN}✅ $api generated successfully${NC}"
        
        # Validate the generated JSON
        output_file="$OUTPUT_DIR/$api.json"
        if [ -f "$output_file" ]; then
            # Check if it's valid JSON
            if jq empty "$output_file" 2>/dev/null; then
                echo -e "${GREEN}✅ $api JSON is valid${NC}"
                
                # Show basic info
                title=$(jq -r '.info.title' "$output_file" 2>/dev/null || echo "Unknown")
                version=$(jq -r '.info.version' "$output_file" 2>/dev/null || echo "Unknown")
                paths_count=$(jq '.paths | length' "$output_file" 2>/dev/null || echo "0")
                
                echo "  📋 Title: $title"
                echo "  🏷️  Version: $version"
                echo "  🛣️  Paths: $paths_count"
            else
                echo -e "${RED}❌ $api JSON is invalid${NC}"
                exit 1
            fi
        else
            echo -e "${RED}❌ $api output file not found${NC}"
            exit 1
        fi
    else
        echo -e "${RED}❌ Failed to generate $api${NC}"
        exit 1
    fi
done

echo -e "\n${GREEN}🎉 All OpenAPI specifications generated successfully!${NC}"
echo ""
echo "Generated files:"
ls -la "$OUTPUT_DIR/"

echo ""
echo "You can now:"
echo "  1. View the JSON files in $OUTPUT_DIR/"
echo "  2. Import them into API tools like Postman or Insomnia"
echo "  3. Generate client SDKs using OpenAPI Generator"
echo "  4. Use them for API documentation"

# Optional: Generate documentation previews if redoc-cli is available
if command -v redoc-cli &> /dev/null; then
    echo ""
    echo "🌐 Generating HTML documentation previews..."
    mkdir -p docs-preview
    
    for api in "${APIS[@]}"; do
        input_file="$OUTPUT_DIR/$api.json"
        output_file="docs-preview/$api.html"
        
        if redoc-cli build "$input_file" --output "$output_file" 2>/dev/null; then
            echo -e "${GREEN}✅ Generated HTML docs for $api${NC}"
        else
            echo -e "${YELLOW}⚠️  Could not generate HTML docs for $api${NC}"
        fi
    done
    
    if [ -n "$(ls -A docs-preview 2>/dev/null)" ]; then
        echo "HTML documentation available in docs-preview/"
    fi
else
    echo ""
    echo "💡 Tip: Install redoc-cli to generate HTML documentation previews:"
    echo "  npm install -g redoc-cli"
fi