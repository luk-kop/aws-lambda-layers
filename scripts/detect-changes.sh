#!/bin/bash
# Detect changed Lambda layers between commits or branches.
#
# Usage:
#   detect-changes.sh pr <base_ref>    - Compare HEAD against base branch (for PRs)
#   detect-changes.sh push             - Compare HEAD against HEAD~1 (for push to main)
#
# Output (JSON to stdout):
#   {
#     "layers": ["common", "utils"],
#     "matrix": [
#       {"name": "common", "version": "1.1"},
#       {"name": "utils", "version": "2.0"}
#     ],
#     "build_matrix": {
#       "include": [
#         {"layer": "common", "version": "1.1", "python": "3.12", "arch": "x86_64"},
#         {"layer": "common", "version": "1.1", "python": "3.12", "arch": "arm64"}
#       ]
#     },
#     "has_changes": true
#   }
#
# Exit codes:
#   0 - Success
#   1 - Error
#
# Validates: Requirements 1.1, 1.2, 5.1, 5.2

set -euo pipefail

usage() {
    echo "Usage: $0 <mode> [base_ref]"
    echo ""
    echo "Modes:"
    echo "  pr <base_ref>  - Compare HEAD against base branch (for PRs)"
    echo "  push           - Compare HEAD against HEAD~1 (for push to main)"
    echo ""
    echo "Output: JSON with 'layers' array, 'matrix' array with versions, 'build_matrix' for GitHub Actions, and 'has_changes' boolean"
    exit 1
}

# Extract version from pyproject.toml using Python
# Args: $1 = layer directory path
get_version() {
    local layer_dir="$1"
    local pyproject="$layer_dir/pyproject.toml"

    if [ ! -f "$pyproject" ]; then
        echo "ERROR: pyproject.toml not found in $layer_dir" >&2
        return 1
    fi

    # Use Python to parse TOML and extract version (no trailing newline)
    python3 -c "
import tomllib
with open('$pyproject', 'rb') as f:
    config = tomllib.load(f)
print(config['project']['version'], end='')
"
}

# Extract build matrix configuration (python_versions and architectures) from pyproject.toml
# Args: $1 = layer directory path
# Output: JSON object with python_versions and architectures arrays
get_build_config() {
    local layer_dir="$1"
    local pyproject="$layer_dir/pyproject.toml"

    if [ ! -f "$pyproject" ]; then
        echo "ERROR: pyproject.toml not found in $layer_dir" >&2
        return 1
    fi

    # Use Python to parse TOML and extract build configuration
    python3 -c "
import tomllib
import json
with open('$pyproject', 'rb') as f:
    config = tomllib.load(f)
lambda_layer = config.get('tool', {}).get('lambda_layer', {})
python_versions = lambda_layer.get('python_versions', ['3.12'])
architectures = lambda_layer.get('architectures', ['x86_64'])
print(json.dumps({'python_versions': python_versions, 'architectures': architectures}), end='')
"
}

# Validate arguments
if [ $# -lt 1 ]; then
    usage
fi

MODE="$1"
BASE_REF="${2:-}"

# Get changed files based on mode
case "$MODE" in
    pr)
        if [ -z "$BASE_REF" ]; then
            echo "ERROR: base_ref required for PR mode" >&2
            usage
        fi
        # Fetch base branch if not available locally
        git fetch origin "$BASE_REF" --depth=1 2>/dev/null || true
        CHANGED_FILES=$(git diff --name-only "origin/$BASE_REF"...HEAD 2>/dev/null || git diff --name-only "$BASE_REF"...HEAD)
        ;;
    push)
        # Compare against previous commit
        CHANGED_FILES=$(git diff --name-only HEAD~1 HEAD 2>/dev/null || echo "")
        ;;
    *)
        echo "ERROR: Unknown mode '$MODE'" >&2
        usage
        ;;
esac

# Filter to only layers/* paths and extract unique layer names
# Use tr to remove any carriage returns and ensure clean output
LAYERS=$(echo "$CHANGED_FILES" | grep '^layers/' | cut -d'/' -f2 | sort -u | grep -v '^$' | tr -d '\r' || echo "")

# Build JSON output
if [ -z "$LAYERS" ]; then
    echo '{"layers": [], "matrix": [], "build_matrix": {"include": []}, "has_changes": false}'
else
    # Convert newline-separated list to JSON array
    LAYERS_JSON=$(echo "$LAYERS" | jq -R -s -c 'split("\n") | map(select(length > 0))')

    # Build matrix array and build_matrix - collect all layer objects first, then combine
    MATRIX_ITEMS=""
    BUILD_MATRIX_ITEMS=""
    while IFS= read -r layer; do
        if [ -z "$layer" ]; then
            continue
        fi

        layer_dir="layers/$layer"

        # Get version from pyproject.toml
        version=$(get_version "$layer_dir") || {
            echo "ERROR: Failed to get version for layer '$layer'" >&2
            exit 1
        }

        # Build JSON object for this layer (simple matrix)
        item=$(jq -n -c --arg name "$layer" --arg version "$version" '{name: $name, version: $version}')

        if [ -z "$MATRIX_ITEMS" ]; then
            MATRIX_ITEMS="$item"
        else
            MATRIX_ITEMS="$MATRIX_ITEMS,$item"
        fi

        # Get build configuration (python_versions and architectures) for expanded build_matrix
        build_config=$(get_build_config "$layer_dir") || {
            echo "ERROR: Failed to get build config for layer '$layer'" >&2
            exit 1
        }

        # Generate Cartesian product of python_versions × architectures for this layer
        # Each combination becomes an entry in the build_matrix
        layer_build_items=$(echo "$build_config" | jq -c --arg layer "$layer" --arg version "$version" '
            [.python_versions[] as $py | .architectures[] as $arch |
             {layer: $layer, version: $version, python: $py, arch: $arch}] | .[]
        ')

        # Append each build item to BUILD_MATRIX_ITEMS
        while IFS= read -r build_item; do
            if [ -z "$build_item" ]; then
                continue
            fi
            if [ -z "$BUILD_MATRIX_ITEMS" ]; then
                BUILD_MATRIX_ITEMS="$build_item"
            else
                BUILD_MATRIX_ITEMS="$BUILD_MATRIX_ITEMS,$build_item"
            fi
        done <<< "$layer_build_items"
    done <<< "$LAYERS"

    MATRIX_JSON="[$MATRIX_ITEMS]"
    BUILD_MATRIX_JSON="{\"include\": [$BUILD_MATRIX_ITEMS]}"

    # Output final JSON using jq to ensure proper formatting
    jq -n -c --argjson layers "$LAYERS_JSON" --argjson matrix "$MATRIX_JSON" --argjson build_matrix "$BUILD_MATRIX_JSON" \
        '{layers: $layers, matrix: $matrix, build_matrix: $build_matrix, has_changes: true}'
fi
