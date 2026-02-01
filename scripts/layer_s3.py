#!/usr/bin/env python3
"""S3 artifact operations for Lambda layers.

Provides utilities for checking and uploading layer artifacts to S3.

CLI Usage:
    layer_s3.py check <name> <version> <bucket> [--prefix PREFIX]
    layer_s3.py version-exists <name> <version> <bucket> [--prefix PREFIX]
    layer_s3.py upload <name> <version> <bucket> [--prefix PREFIX] [--dry-run]

Public Functions:
    s3_object_exists(s3_client, bucket: str, key: str) -> bool
    check_artifacts(name: str, version: str, bucket: str, prefix: str) -> bool
    check_version_exists(name: str, version: str, bucket: str, prefix: str) -> bool
    upload_layer(name: str, version: str, bucket: str, prefix: str, dry_run: bool) -> bool
    get_file_size_human(path: Path) -> str
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import TYPE_CHECKING

import boto3
from botocore.exceptions import ClientError

from layer_config import get_build_matrix

if TYPE_CHECKING:
    from mypy_boto3_s3 import S3Client

# Directory containing all layer definitions
LAYERS_DIR = Path("layers")

# Build directory root (convention shared with build-layer.sh)
BUILD_ROOT = Path(".build")

# S3 prefix for immutable release artifacts
RELEASE_PREFIX = "layers"

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(message)s",
)
logger = logging.getLogger(__name__)


# =============================================================================
# Shared S3 utility
# =============================================================================


def s3_object_exists(s3_client: S3Client, bucket: str, key: str) -> bool:
    """Check if an S3 object exists.

    Args:
        s3_client: Boto3 S3 client instance
        bucket: S3 bucket name
        key: S3 object key

    Returns:
        True if object exists, False otherwise

    Raises:
        ClientError: If S3 API call fails (except 404)
    """
    try:
        s3_client.head_object(Bucket=bucket, Key=key)
        return True
    except ClientError as e:
        if e.response["Error"]["Code"] == "404":
            return False
        raise


def check_artifacts(
    name: str,
    version: str,
    bucket: str,
    prefix: str = RELEASE_PREFIX,
) -> bool:
    """Check if all expected artifacts exist in S3.

    Args:
        name: Layer name
        version: Layer version
        bucket: S3 bucket name
        prefix: S3 key prefix (default: "layers")

    Returns:
        True if all artifacts found, False otherwise
    """
    layer_dir = LAYERS_DIR / name

    # Check layer directory exists
    if not layer_dir.exists():
        logger.error(f"❌ ERROR: Layer directory '{layer_dir}' not found")
        return False

    # Check pyproject.toml exists
    pyproject = layer_dir / "pyproject.toml"
    if not pyproject.exists():
        logger.error(f"❌ ERROR: pyproject.toml not found in {layer_dir}")
        return False

    logger.info(f"Checking artifacts for {name} v{version}")
    logger.info(f"  Bucket: s3://{bucket}")
    logger.info(f"  Prefix: {prefix}")
    logger.info("")

    # Get build matrix from config
    matrix = get_build_matrix(layer_dir)

    # Generate expected artifact names
    artifacts = []
    for item in matrix:
        py = item["python"].replace(".", "")
        arch = item["arch"]
        artifacts.append(f"py{py}-{arch}.zip")

    s3_client = boto3.client("s3")

    found = 0
    missing = 0

    logger.info("Expected artifacts:")

    for artifact in artifacts:
        s3_key = f"{prefix}/{name}/{version}/{artifact}"

        if s3_object_exists(s3_client, bucket, s3_key):
            logger.info(f"  ✅ {artifact}")
            found += 1
        else:
            logger.info(f"  ❌ {artifact} (MISSING)")
            missing += 1

    total = found + missing
    logger.info("")
    logger.info(f"Summary: {found}/{total} artifacts found")

    if missing > 0:
        logger.info("")
        logger.error(f"❌ ERROR: {missing} artifact(s) missing")
        logger.info("")
        logger.info("To build and upload missing artifacts:")
        logger.info(f"  ./scripts/build-layer.sh {name} <python> <arch>")
        logger.info(
            f"  python scripts/layer_s3.py upload {name} {version} {bucket} --prefix {prefix}"
        )
        return False

    logger.info("")
    logger.info("✅ All artifacts found")
    return True


def check_version_exists(
    name: str,
    version: str,
    bucket: str,
    prefix: str = RELEASE_PREFIX,
) -> bool:
    """Check if any artifact exists for this layer version in S3.

    Args:
        name: Layer name
        version: Layer version
        bucket: S3 bucket name
        prefix: S3 key prefix (default: "layers")

    Returns:
        True if any artifact exists, False otherwise
    """
    s3_prefix = f"{prefix}/{name}/{version}/"
    s3_client = boto3.client("s3")
    response = s3_client.list_objects_v2(Bucket=bucket, Prefix=s3_prefix, MaxKeys=1)
    return response.get("KeyCount", 0) > 0


def get_file_size_human(path: Path) -> str:
    """Get human-readable file size.

    Args:
        path: Path to the file

    Returns:
        Human-readable size string (e.g., '5.2MB')
    """
    size = path.stat().st_size
    for unit in ["B", "KB", "MB", "GB"]:
        if size < 1024:
            return f"{size:.1f}{unit}"
        size /= 1024
    return f"{size:.1f}TB"


def upload_layer(
    name: str,
    version: str,
    bucket: str,
    prefix: str = RELEASE_PREFIX,
    dry_run: bool = False,
) -> bool:
    """Upload layer artifacts to S3.

    Args:
        name: Layer name
        version: Layer version
        bucket: S3 bucket name
        prefix: S3 key prefix (default: "layers")
        dry_run: If True, show what would be uploaded without uploading

    Returns:
        True if all uploads succeeded, False otherwise
    """
    build_dir = BUILD_ROOT / name / "dist"

    # Check build directory exists
    if not build_dir.exists():
        logger.error(f"No build artifacts found in {build_dir}")
        logger.info("Run build-layer.sh first to create artifacts.")
        return False

    # Find ZIP files
    zip_files = list(build_dir.glob("*.zip"))
    if not zip_files:
        logger.error(f"No ZIP artifacts found in {build_dir}")
        return False

    # Print header
    if dry_run:
        logger.info(f"[DRY-RUN] Uploading layer: {name} v{version}")
    else:
        logger.info(f"Uploading layer: {name} v{version}")
    logger.info(f"  Bucket: s3://{bucket}")
    logger.info(f"  Prefix: {prefix}")

    s3_client = boto3.client("s3")

    uploaded = 0
    pending = 0  # Count of files that would be uploaded (dry-run mode only)
    failed = 0

    for zip_file in sorted(zip_files):
        filename = zip_file.name
        s3_key = f"{prefix}/{name}/{version}/{filename}"
        s3_path = f"s3://{bucket}/{s3_key}"

        # Check immutability for release artifacts (prefix=RELEASE_PREFIX)
        if prefix == RELEASE_PREFIX:
            if s3_object_exists(s3_client, bucket, s3_key):
                logger.error(f"  ✗ {filename} - ALREADY EXISTS")
                logger.error(f"    Cannot overwrite immutable artifact: {s3_path}")
                logger.error("    Release a new version instead.")
                failed += 1
                continue
        else:
            # For test prefix, warn if overwriting
            if s3_object_exists(s3_client, bucket, s3_key):
                logger.warning(f"  ⚠ {filename} - overwriting existing test artifact")

        if dry_run:
            file_size = get_file_size_human(zip_file)
            logger.info(
                f"  [DRY-RUN] Would upload: {filename} ({file_size}) -> {s3_path}"
            )
            pending += 1
        else:
            logger.info(f"  Uploading: {filename} -> {s3_path}")
            try:
                s3_client.upload_file(str(zip_file), bucket, s3_key)
                logger.info(f"  ✓ {filename}")
                uploaded += 1
            except ClientError as e:
                logger.error(f"  ✗ {filename} - upload failed: {e}")
                failed += 1

    # Print summary
    logger.info("Summary:")
    if dry_run:
        logger.info(f"  Pending: {pending}")
    else:
        logger.info(f"  Uploaded: {uploaded}")
    if failed > 0:
        logger.error(f"  Failed: {failed}")

    if failed > 0:
        logger.error("Some artifacts failed to upload")
        return False

    if dry_run:
        logger.info(
            f"[DRY-RUN] Would upload {name} v{version} to s3://{bucket}/{prefix}/"
        )
    else:
        logger.info(f"✓ Uploaded {name} v{version} to s3://{bucket}/{prefix}/")

    return True


# =============================================================================
# CLI Implementation
# =============================================================================


def main() -> int:
    """Main entry point.

    Returns:
        0 on success, 1 on error
    """
    parser = argparse.ArgumentParser(
        description="S3 artifact operations for Lambda layers.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s check common 1.0 my-bucket
  %(prog)s version-exists common 1.0 my-bucket
  %(prog)s version-exists common 1.0 my-bucket --prefix test/123
  %(prog)s upload common 1.0 my-bucket
  %(prog)s upload common 1.0 my-bucket --prefix test/123 --dry-run
""",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # check command
    check_parser = subparsers.add_parser(
        "check",
        help="Check if all expected artifacts exist in S3",
        description="Verifies all expected artifacts exist based on build matrix in pyproject.toml.",
    )
    check_parser.add_argument("name", help="Layer name (e.g., 'common')")
    check_parser.add_argument("version", help="Layer version (e.g., '1.0')")
    check_parser.add_argument("bucket", help="S3 bucket name")
    check_parser.add_argument(
        "--prefix",
        default=RELEASE_PREFIX,
        help=f"S3 key prefix (default: '{RELEASE_PREFIX}')",
    )

    # version-exists command
    version_exists_parser = subparsers.add_parser(
        "version-exists",
        help="Check if any artifact exists for a version",
        description="Checks if any artifact exists for this version in S3. Exit 0 if exists, 1 if not.",
    )
    version_exists_parser.add_argument("name", help="Layer name (e.g., 'common')")
    version_exists_parser.add_argument("version", help="Layer version (e.g., '1.0')")
    version_exists_parser.add_argument("bucket", help="S3 bucket name")
    version_exists_parser.add_argument(
        "--prefix",
        default=RELEASE_PREFIX,
        help=f"S3 key prefix (default: '{RELEASE_PREFIX}')",
    )

    # upload command
    upload_parser = subparsers.add_parser(
        "upload",
        help="Upload layer artifacts to S3",
        description="Uploads built layer artifacts to S3 with immutability enforcement.",
    )
    upload_parser.add_argument("name", help="Layer name (e.g., 'common')")
    upload_parser.add_argument("version", help="Layer version (e.g., '1.0')")
    upload_parser.add_argument("bucket", help="S3 bucket name")
    upload_parser.add_argument(
        "--prefix",
        default=RELEASE_PREFIX,
        help=f"S3 key prefix (default: '{RELEASE_PREFIX}')",
    )
    upload_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be uploaded without actually uploading",
    )

    args = parser.parse_args()

    if args.command == "check":
        success = check_artifacts(
            name=args.name,
            version=args.version,
            bucket=args.bucket,
            prefix=args.prefix,
        )
        return 0 if success else 1

    elif args.command == "version-exists":
        if check_version_exists(
            name=args.name,
            version=args.version,
            bucket=args.bucket,
            prefix=args.prefix,
        ):
            logger.info(
                f"Version {args.version} exists for layer '{args.name}' "
                f"in s3://{args.bucket}/{args.prefix}/"
            )
            return 0
        else:
            logger.info(
                f"Version {args.version} does not exist for layer '{args.name}' "
                f"in s3://{args.bucket}/{args.prefix}/"
            )
            return 1

    elif args.command == "upload":
        success = upload_layer(
            name=args.name,
            version=args.version,
            bucket=args.bucket,
            prefix=args.prefix,
            dry_run=args.dry_run,
        )
        return 0 if success else 1

    return 1


if __name__ == "__main__":
    sys.exit(main())
