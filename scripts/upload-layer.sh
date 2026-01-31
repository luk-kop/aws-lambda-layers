#!/bin/bash
# Usage: ./scripts/upload-layer.sh <name> <version> <bucket> [prefix]
# Default prefix: layers
#
# Uploads built layer artifacts to S3 with immutability enforcement.
# For release artifacts (prefix=layers), existing artifacts cannot be overwritten.
# For test artifacts (prefix=test/*), overwrites are allowed.
#
# Requirements: 2.6, 2.7, 7.1, 7.2

set -euo pipefail

# Color output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[0;33m'
NC='\033[0m' # No Color

usage() {
    echo "Usage: $0 <name> <version> <bucket> [prefix]"
    echo ""
    echo "Uploads layer artifacts to S3."
    echo ""
    echo "Arguments:"
    echo "  name      Layer name (e.g., 'common')"
    echo "  version   Layer version (e.g., '1.0')"
    echo "  bucket    S3 bucket name"
    echo "  prefix    S3 key prefix (default: 'layers')"
    echo ""
    echo "S3 Key Format:"
    echo "  <prefix>/<name>/<version>/py<python>-<arch>.zip"
    echo ""
    echo "Examples:"
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

BUILD_DIR=".build/$LAYER_NAME/dist"

# Check build directory exists
if [ ! -d "$BUILD_DIR" ]; then
    echo -e "${RED}ERROR: No build artifacts found in $BUILD_DIR${NC}"
    echo "Run build-layer.sh first to create artifacts."
    exit 1
fi

# Check for ZIP files
ZIP_COUNT=$(find "$BUILD_DIR" -name "*.zip" 2>/dev/null | wc -l)
if [ "$ZIP_COUNT" -eq 0 ]; then
    echo -e "${RED}ERROR: No ZIP artifacts found in $BUILD_DIR${NC}"
    exit 1
fi

echo "Uploading layer: $LAYER_NAME v$VERSION"
echo "  Bucket: s3://$BUCKET"
echo "  Prefix: $PREFIX"
echo ""

UPLOADED=0
SKIPPED=0
FAILED=0

for ZIP_FILE in "$BUILD_DIR"/*.zip; do
    [ -f "$ZIP_FILE" ] || continue

    FILENAME=$(basename "$ZIP_FILE")
    S3_KEY="$PREFIX/$LAYER_NAME/$VERSION/$FILENAME"
    S3_PATH="s3://$BUCKET/$S3_KEY"

    # Check immutability for release artifacts (prefix=layers)
    if [ "$PREFIX" = "layers" ]; then
        if aws s3 ls "$S3_PATH" >/dev/null 2>&1; then
            echo -e "${RED}  ✗ $FILENAME - ALREADY EXISTS${NC}"
            echo -e "${RED}    Cannot overwrite immutable artifact: $S3_PATH${NC}"
            echo -e "${RED}    Release a new version instead.${NC}"
            FAILED=$((FAILED + 1))
            continue
        fi
    else
        # For test prefix, warn if overwriting
        if aws s3 ls "$S3_PATH" >/dev/null 2>&1; then
            echo -e "${YELLOW}  ⚠ $FILENAME - overwriting existing test artifact${NC}"
        fi
    fi

    # Upload to S3
    echo "  Uploading: $FILENAME -> $S3_PATH"
    if aws s3 cp "$ZIP_FILE" "$S3_PATH" --quiet; then
        echo -e "${GREEN}  ✓ $FILENAME${NC}"
        UPLOADED=$((UPLOADED + 1))
    else
        echo -e "${RED}  ✗ $FILENAME - upload failed${NC}"
        FAILED=$((FAILED + 1))
    fi
done

echo ""
echo "Summary:"
echo "  Uploaded: $UPLOADED"
[ "$SKIPPED" -gt 0 ] && echo "  Skipped:  $SKIPPED"
[ "$FAILED" -gt 0 ] && echo -e "${RED}  Failed:   $FAILED${NC}"

if [ "$FAILED" -gt 0 ]; then
    echo ""
    echo -e "${RED}ERROR: Some artifacts failed to upload${NC}"
    exit 1
fi

echo ""
echo -e "${GREEN}✓ Uploaded $LAYER_NAME v$VERSION to s3://$BUCKET/$PREFIX/${NC}"
