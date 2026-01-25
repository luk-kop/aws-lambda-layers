#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LAYERS_DIR="${SCRIPT_DIR}/../layers"

# Find all directories containing pyproject.toml or uv.lock
while IFS= read -r -d '' layer_dir; do
    layer_path="${layer_dir#"${LAYERS_DIR}/"}"
    "${SCRIPT_DIR}/build-layer.sh" "${layer_path}"
done < <(find "${LAYERS_DIR}" -type f \( -name "pyproject.toml" -o -name "uv.lock" \) -printf '%h\0' | sort -uz)

echo "All layers built successfully"
