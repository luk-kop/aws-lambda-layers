#!/bin/bash
# Usage: ./scripts/build-layer.sh <name> <python> <arch>
# Output: .build/<name>/dist/py<python>-<arch>.zip
#
# Builds a Lambda layer ZIP artifact for a specific Python version and architecture.
# Reference: https://docs.astral.sh/uv/guides/integration/aws-lambda/#deploying-a-zip-archive

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 <name> <python> <arch>"
    echo ""
    echo "Builds a Lambda layer ZIP artifact."
    echo ""
    echo "Arguments:"
    echo "  name      Layer name (e.g., 'common')"
    echo "  python    Python version (e.g., '3.12')"
    echo "  arch      Architecture ('x86_64' or 'arm64')"
    echo ""
    echo "Output:"
    echo "  .build/<name>/dist/py<python>-<arch>.zip"
    echo ""
    echo "Example:"
    echo "  $0 common 3.12 x86_64"
    exit 1
}

# Check arguments
if [ $# -lt 3 ]; then
    echo -e "${RED}ERROR: Missing required arguments${NC}"
    usage
fi

LAYER_NAME=$1
PYTHON_VERSION=$2
ARCH=$3

LAYER_DIR="layers/$LAYER_NAME"
BUILD_DIR=".build/$LAYER_NAME"
PYTHON_SHORT="${PYTHON_VERSION//./}"
ARTIFACT_NAME="py${PYTHON_SHORT}-${ARCH}.zip"

# Check layer directory exists
if [ ! -d "$LAYER_DIR" ]; then
    echo -e "${RED}ERROR: Layer directory '$LAYER_DIR' not found${NC}"
    exit 1
fi

# Check pyproject.toml exists
if [ ! -f "$LAYER_DIR/pyproject.toml" ]; then
    echo -e "${RED}ERROR: pyproject.toml not found in $LAYER_DIR${NC}"
    exit 1
fi

echo "Building layer: $LAYER_NAME (Python $PYTHON_VERSION, $ARCH)"

# Validate configuration using validate-config.py
echo "  Validating configuration..."
if ! python3 scripts/validate-config.py validate "$LAYER_DIR"; then
    echo -e "${RED}ERROR: Configuration validation failed${NC}"
    exit 1
fi

# Get platform from config
PLATFORM=$(python3 scripts/validate-config.py platform "$LAYER_DIR" --arch "$ARCH")
echo "  Platform: $PLATFORM"

# Clean and create build directory
echo "  Preparing build directory..."
rm -rf "$BUILD_DIR/python"
mkdir -p "$BUILD_DIR/python" "$BUILD_DIR/dist"

# Export requirements (frozen lockfile, no dev dependencies)
echo "  Exporting requirements..."
(cd "$LAYER_DIR" && uv export --frozen --no-dev --no-editable -o requirements.txt)

# Check if there are any dependencies to install
if [ -s "$LAYER_DIR/requirements.txt" ]; then
    echo "  Installing dependencies..."
    uv pip install \
        --no-installer-metadata \
        --no-compile-bytecode \
        --python-platform "$PLATFORM" \
        --python "$PYTHON_VERSION" \
        --target "$BUILD_DIR/python" \
        -r "$LAYER_DIR/requirements.txt"
else
    echo -e "${YELLOW}  No dependencies to install${NC}"
fi

# Copy src/ contents if exists and not empty
if [ -d "$LAYER_DIR/src" ] && [ "$(ls -A "$LAYER_DIR/src" 2>/dev/null)" ]; then
    echo "  Copying src/ contents..."
    cp -r "$LAYER_DIR/src/"* "$BUILD_DIR/python/"
fi

# Cleanup unnecessary files to reduce layer size
echo "  Cleaning up unnecessary files..."
find "$BUILD_DIR/python" -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR/python" -type d -name "*.dist-info" -exec rm -rf {} + 2>/dev/null || true
find "$BUILD_DIR/python" -type f -name "*.pyc" -delete 2>/dev/null || true

# Create ZIP (Lambda layer expects python/ at root)
echo "  Creating ZIP archive..."
(cd "$BUILD_DIR" && zip -rq "dist/$ARTIFACT_NAME" python/)

# Cleanup requirements.txt
rm -f "$LAYER_DIR/requirements.txt"

# Report artifact size
ARTIFACT_PATH="$BUILD_DIR/dist/$ARTIFACT_NAME"
ARTIFACT_SIZE=$(du -h "$ARTIFACT_PATH" | cut -f1)

echo -e "${GREEN}✓ Built: $ARTIFACT_PATH ($ARTIFACT_SIZE)${NC}"
