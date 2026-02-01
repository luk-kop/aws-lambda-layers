#!/bin/bash
# Usage: ./scripts/check-artifacts.sh <name> <version> <bucket> [prefix]
# Default prefix: layers
#
# Verifies all expected layer artifacts exist in S3 based on the build matrix
# defined in pyproject.toml. Useful for validating releases before Terraform deployment.
#
# Exit codes:
#   0 - All artifacts found
#   1 - Some artifacts missing or error

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 <name> <version> <bucket> [prefix]"
    echo ""
    echo "Verifies all expected layer artifacts exist in S3."
    echo ""
    echo "Arguments:"
    echo "  name      Layer name (e.g., 'common')"
    echo "  version   Layer version (e.g., '1.0')"
    echo "  bucket    S3 bucket name"
    echo "  prefix    S3 key prefix (default: 'layers')"
    echo ""
    echo "Example:"
    echo "  $0 common 1.0 my-lambda-layers"
    echo "  $0 common 1.0 my-lambda-layers test/123"
    exit 1
}

# Check arguments
if [ $# -lt 3 ]; then
    echo -e "${RED}ERROR: Missing required arguments${NC}"
    usage
fi

LAYER_NAME=$1
VERSION=$2
BUCKET=$3
PREFIX=${4:-layers}

LAYER_DIR="layers/$LAYER_NAME"

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

echo "Checking artifacts for $LAYER_NAME v$VERSION"
echo "  Bucket: s3://$BUCKET"
echo "  Prefix: $PREFIX"
echo ""

# Get build matrix from config
MATRIX=$(python3 scripts/validate-config.py matrix "$LAYER_DIR")

# Generate list of expected artifacts
ARTIFACTS=$(echo "$MATRIX" | python3 -c "
import sys
import json

data = json.load(sys.stdin)
for item in data.get('include', []):
    py = item['python'].replace('.', '')
    arch = item['arch']
    print(f'py{py}-{arch}.zip')
")

FOUND=0
MISSING=0
TOTAL=0

echo "Expected artifacts:"

for ARTIFACT in $ARTIFACTS; do
    TOTAL=$((TOTAL + 1))
    S3_KEY="$PREFIX/$LAYER_NAME/$VERSION/$ARTIFACT"
    S3_PATH="s3://$BUCKET/$S3_KEY"

    if aws s3 ls "$S3_PATH" >/dev/null 2>&1; then
        echo -e "  ${GREEN}✓${NC} $ARTIFACT"
        FOUND=$((FOUND + 1))
    else
        echo -e "  ${RED}✗${NC} $ARTIFACT (MISSING)"
        MISSING=$((MISSING + 1))
    fi
done

echo ""
echo "Summary: $FOUND/$TOTAL artifacts found"

if [ "$MISSING" -gt 0 ]; then
    echo ""
    echo -e "${RED}ERROR: $MISSING artifact(s) missing${NC}"
    echo ""
    echo "To build and upload missing artifacts:"
    echo "  ./scripts/build-layer.sh $LAYER_NAME <python> <arch>"
    echo "  ./scripts/upload-layer.sh $LAYER_NAME $VERSION $BUCKET $PREFIX"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ All artifacts found${NC}"
