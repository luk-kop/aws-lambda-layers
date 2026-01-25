#!/usr/bin/env bash
set -euo pipefail

# Usage: ./create-layer.sh <name> <version> <python> <arch>
# Example: ./create-layer.sh common 1_0 312 x86_64
#
# Arguments:
#   name    - layer name (e.g., "common", "common-utils")
#   version - version without dot (e.g., "1_0" for 1.0)
#   python  - python version without dot (e.g., "312" for 3.12)
#   arch    - architecture ("x86_64" or "arm64")

NAME="${1:?Usage: $0 <name> <version> <python> <arch>}"
VERSION="${2:?Usage: $0 <name> <version> <python> <arch>}"
PYTHON="${3:?Usage: $0 <name> <version> <python> <arch>}"
ARCH="${4:?Usage: $0 <name> <version> <python> <arch>}"

# Validate arch
if [[ "$ARCH" != "x86_64" && "$ARCH" != "arm64" ]]; then
    echo "Error: arch must be 'x86_64' or 'arm64'"
    exit 1
fi

# Validate version format (X_Y)
if [[ ! "$VERSION" =~ ^[0-9]+_[0-9]+$ ]]; then
    echo "Error: version must be in format X_Y (e.g., 1_0, 2_1)"
    exit 1
fi

# Validate python version format (XYZ, 2-3 digits)
if [[ ! "$PYTHON" =~ ^[0-9]{2,3}$ ]]; then
    echo "Error: python must be 2-3 digits without dots (e.g., 312 for Python 3.12)"
    exit 1
fi

# Transform to PEP 440 format for pyproject.toml
# "1_0" -> "1.0"
PEP_VERSION="${VERSION//_/.}"
# "312" -> "3.12" (insert dot after first character)
PEP_PYTHON="${PYTHON:0:1}.${PYTHON:1}"

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAYER_DIR="${SCRIPT_DIR}/../layers/${NAME}/v${VERSION}/py${PYTHON}/${ARCH}"

if [[ -d "$LAYER_DIR" ]]; then
    echo "Error: Layer already exists: $LAYER_DIR"
    exit 1
fi

echo "Creating layer: ${NAME}/v${VERSION}/py${PYTHON}/${ARCH}"

mkdir -p "$LAYER_DIR"

cat > "${LAYER_DIR}/pyproject.toml" << EOF
[project]
name = "${NAME}"
version = "${PEP_VERSION}"
requires-python = "==${PEP_PYTHON}.*"
dependencies = []
EOF

echo "Created: ${LAYER_DIR}/pyproject.toml"
echo ""
echo "Next steps:"
echo "  cd ${LAYER_DIR}"
echo "  uv add <package-name>"
