#!/usr/bin/env bash
set -euo pipefail

# Usage: ./build-layer.sh <name/vX_Y/pyXYZ/arch>
# Example: ./build-layer.sh common/v1_0/py312/x86_64

LAYER_PATH="${1:?Usage: $0 <name/vX_Y/pyXYZ/arch>}"
LAYERS_DIR="$(cd "$(dirname "$0")/../layers" && pwd)"
BUILD_DIR="$(cd "$(dirname "$0")/.." && pwd)/terraform/.build"

LAYER_SRC="${LAYERS_DIR}/${LAYER_PATH}"

if [[ ! -d "${LAYER_SRC}" ]]; then
    echo "Error: Layer directory not found: ${LAYER_SRC}"
    exit 1
fi

# Extract components from path
# Path format: name/vX_Y/pyXYZ/arch
IFS='/' read -ra PATH_PARTS <<< "${LAYER_PATH}"
if [[ ${#PATH_PARTS[@]} -lt 4 ]]; then
    echo "Error: Invalid path format. Expected: name/vX_Y/pyXYZ/arch"
    exit 1
fi

LAYER_NAME="${PATH_PARTS[0]}"
VERSION_DIR="${PATH_PARTS[1]}"   # e.g., "v1_0"
PYTHON_DIR="${PATH_PARTS[2]}"    # e.g., "py312"
ARCH="${PATH_PARTS[3]}"          # e.g., "x86_64"

# Validate path format
if [[ ! "$VERSION_DIR" =~ ^v[0-9]+_[0-9]+$ ]]; then
    echo "Error: Version directory must be in format vX_Y (e.g., v1_0)"
    exit 1
fi

if [[ ! "$PYTHON_DIR" =~ ^py[0-9]{2,3}$ ]]; then
    echo "Error: Python directory must be in format pyXYZ (e.g., py312)"
    exit 1
fi

# Extract version and python from directory names
VERSION_PATH="${VERSION_DIR#v}"      # "1_0"
PYTHON_PATH="${PYTHON_DIR#py}"       # "312"

# Transform for pyproject.toml validation:
# "1_0" -> "1.0"
LAYER_VERSION="${VERSION_PATH//_/.}"
# "312" -> "3.12" (insert dot after first character)
PYTHON_VERSION="${PYTHON_PATH:0:1}.${PYTHON_PATH:1}"

# Generate layer key for build output: name-vX_Y-pyXYZ-arch
LAYER_KEY="${LAYER_NAME}-v${VERSION_PATH}-py${PYTHON_PATH}-${ARCH}"
LAYER_BUILD="${BUILD_DIR}/${LAYER_KEY}"

# Validate pyproject.toml exists and matches path
if [[ ! -f "${LAYER_SRC}/pyproject.toml" ]]; then
    echo "Error: pyproject.toml not found in ${LAYER_SRC}"
    exit 1
fi

echo "Validating pyproject.toml..."

file_name=$(grep -oP '^name\s*=\s*"\K[^"]+' "${LAYER_SRC}/pyproject.toml" || echo "")
file_version=$(grep -oP '^version\s*=\s*"\K[^"]+' "${LAYER_SRC}/pyproject.toml" || echo "")
file_python=$(grep -oP 'requires-python\s*=\s*"[>=<]*\K[0-9]+\.[0-9]+' "${LAYER_SRC}/pyproject.toml" || echo "")

errors=""
[[ -n "$file_name" && "$file_name" != "$LAYER_NAME" ]] && errors+="  name: '$file_name' != '$LAYER_NAME'\n"
[[ -n "$file_version" && "$file_version" != "$LAYER_VERSION" ]] && errors+="  version: '$file_version' != '$LAYER_VERSION'\n"
[[ -n "$file_python" && "$file_python" != "$PYTHON_VERSION" ]] && errors+="  requires-python: '$file_python' != '$PYTHON_VERSION'\n"

if [[ -n "$errors" ]]; then
    echo "Error: pyproject.toml does not match path:"
    echo -e "$errors"
    echo "Path expects: name=$LAYER_NAME, version=$LAYER_VERSION, python=$PYTHON_VERSION"
    exit 1
fi
echo "  pyproject.toml OK"

# Map arch to uv platform
case "${ARCH}" in
    x86_64)
        UV_PLATFORM="x86_64-manylinux2014"
        ;;
    arm64)
        UV_PLATFORM="aarch64-manylinux2014"
        ;;
    *)
        echo "Error: Unknown architecture: ${ARCH}"
        exit 1
        ;;
esac

echo "Building layer: ${LAYER_PATH} -> ${LAYER_KEY}"
echo "  Python: ${PYTHON_VERSION}, Arch: ${ARCH} (${UV_PLATFORM})"

cd "${LAYER_SRC}"

mkdir -p "${BUILD_DIR}"
rm -rf "${LAYER_BUILD}"
mkdir -p "${LAYER_BUILD}/python"

TEMP_REQUIREMENTS=$(mktemp)
trap "rm -f ${TEMP_REQUIREMENTS}" EXIT

if [[ -f "uv.lock" ]]; then
    echo "Installing dependencies from uv.lock..."
    uv export --frozen --no-hashes --no-dev -o "${TEMP_REQUIREMENTS}"
    uv pip install \
        --target "${LAYER_BUILD}/python" \
        --python-platform "${UV_PLATFORM}" \
        --python-version "${PYTHON_VERSION}" \
        -r "${TEMP_REQUIREMENTS}"
elif [[ -f "requirements.txt" ]]; then
    echo "Installing dependencies from requirements.txt..."
    uv pip install \
        --target "${LAYER_BUILD}/python" \
        --python-platform "${UV_PLATFORM}" \
        --python-version "${PYTHON_VERSION}" \
        -r requirements.txt
fi

if [[ -d "src" ]]; then
    echo "Copying custom source code..."
    cp -r src/* "${LAYER_BUILD}/python/"
fi

# Validate build output is not empty
if [[ -z "$(ls -A "${LAYER_BUILD}/python" 2>/dev/null)" ]]; then
    echo "Warning: Layer build output is empty (no dependencies or src/)"
fi

# Create build marker for Terraform trigger
# Contains uv.lock hash so Terraform can detect if rebuild is needed
if [[ -f "uv.lock" ]]; then
    sha256sum "uv.lock" | cut -d' ' -f1 > "${LAYER_BUILD}/.buildinfo"
else
    echo "no-lockfile" > "${LAYER_BUILD}/.buildinfo"
fi

echo "Layer built: ${LAYER_BUILD}"
