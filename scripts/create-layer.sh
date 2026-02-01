#!/bin/bash
# Usage: ./scripts/create-layer.sh <name>
# Creates: layers/<name>/pyproject.toml, uv.lock, src/
#
# This script creates a new Lambda layer with the flat structure:
#   layers/<name>/
#   ├── pyproject.toml     # Dependencies and [tool.lambda_layer] config
#   ├── uv.lock            # Locked dependency versions
#   └── src/               # Optional custom Python code

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 <name>"
    echo ""
    echo "Creates a new Lambda layer with template files."
    echo ""
    echo "Arguments:"
    echo "  name    Layer name (e.g., 'utils', 'common')"
    echo ""
    echo "Example:"
    echo "  $0 utils"
    exit 1
}

# Check arguments
if [ $# -lt 1 ]; then
    echo -e "${RED}ERROR: Layer name is required${NC}"
    usage
fi

LAYER_NAME=$1
LAYER_DIR="layers/$LAYER_NAME"

# Validate layer name (alphanumeric, hyphens, underscores)
if [[ ! "$LAYER_NAME" =~ ^[a-zA-Z][a-zA-Z0-9_-]*$ ]]; then
    echo -e "${RED}ERROR: Invalid layer name '$LAYER_NAME'${NC}"
    echo "Layer name must start with a letter and contain only letters, numbers, hyphens, and underscores."
    exit 1
fi

# Check if layer already exists
if [ -d "$LAYER_DIR" ]; then
    echo -e "${RED}ERROR: Layer '$LAYER_NAME' already exists at $LAYER_DIR${NC}"
    exit 1
fi

echo "Creating layer: $LAYER_NAME"

# Create layer directory structure
mkdir -p "$LAYER_DIR/src"

# Create pyproject.toml with template
cat > "$LAYER_DIR/pyproject.toml" << EOF
[project]
name = "$LAYER_NAME"
version = "1.0"
requires-python = ">=3.11"
dependencies = []

[tool.lambda_layer]
python_versions = ["3.12"]
architectures = ["x86_64"]
platforms = { x86_64 = "x86_64-manylinux2014", arm64 = "aarch64-manylinux2014" }
EOF

echo "  Created: $LAYER_DIR/pyproject.toml"

# Initialize uv.lock
echo "  Initializing lockfile..."
(cd "$LAYER_DIR" && uv lock)

echo "  Created: $LAYER_DIR/uv.lock"
echo "  Created: $LAYER_DIR/src/"

echo -e "${GREEN}✓ Created layer: $LAYER_DIR${NC}"
echo ""
echo "Next steps:"
echo "  1. Add dependencies: cd $LAYER_DIR && uv add <package>"
echo "  2. Update python_versions/architectures in pyproject.toml if needed"
echo "  3. Add custom code to src/ directory (optional)"
echo "  4. Build locally: ./scripts/build-layer.sh $LAYER_NAME 3.12 x86_64"
echo "  5. Release: git tag layer/$LAYER_NAME/1.0 && git push origin --tags"
