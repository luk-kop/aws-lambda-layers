#!/usr/bin/env python3
"""Validate layer configuration from pyproject.toml.

This script validates Lambda layer configurations and provides utilities
for extracting build information from pyproject.toml files.

Usage:
    validate-config.py validate <layer_dir>
    validate-config.py platform <layer_dir> --arch <arch>
    validate-config.py matrix <layer_dir>
    validate-config.py version <layer_dir>
    validate-config.py check-version <layer_dir> --bucket <bucket> [--prefix layers]
"""

import argparse
import json
import logging
import subprocess
import sys
import tomllib
from pathlib import Path

from packaging.specifiers import SpecifierSet

# Configure logging with nice formatting
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)


def load_config(layer_dir: Path) -> dict:
    """Load and parse pyproject.toml.

    Args:
        layer_dir: Path to the layer directory containing pyproject.toml

    Returns:
        Parsed configuration dictionary

    Raises:
        FileNotFoundError: If pyproject.toml doesn't exist
    """
    pyproject = layer_dir / "pyproject.toml"
    if not pyproject.exists():
        raise FileNotFoundError(f"pyproject.toml not found in {layer_dir}")

    with open(pyproject, "rb") as f:
        return tomllib.load(f)


def validate_config(config: dict, layer_name: str) -> list[str]:
    """Validate layer configuration.

    Args:
        config: Parsed pyproject.toml configuration
        layer_name: Name of the layer for error messages

    Returns:
        List of validation error messages (empty if valid)
    """
    errors = []

    # Check required sections
    if "project" not in config:
        errors.append(f"{layer_name}: Missing [project] section")
        return errors

    if "tool" not in config or "lambda_layer" not in config.get("tool", {}):
        errors.append(f"{layer_name}: Missing [tool.lambda_layer] section")
        return errors

    layer_config = config["tool"]["lambda_layer"]

    # Check required fields in [tool.lambda_layer]
    required_fields = ["python_versions", "architectures", "platforms"]
    for field in required_fields:
        if field not in layer_config:
            errors.append(
                f"{layer_name}: Missing required field '{field}' in [tool.lambda_layer]"
            )

    if errors:
        return errors

    # Validate project name matches directory name
    project_name = config["project"].get("name")
    if not project_name:
        errors.append(f"{layer_name}: Missing 'name' field in [project] section")
    elif project_name != layer_name:
        errors.append(
            f"{layer_name}: Project name '{project_name}' "
            f"does not match directory name '{layer_name}'"
        )

    # Validate python_versions against requires-python
    requires_python = config["project"].get("requires-python", ">=3.11")
    spec = SpecifierSet(requires_python)

    for version in layer_config["python_versions"]:
        if not spec.contains(version):
            errors.append(
                f"{layer_name}: Python {version} not allowed by requires-python {requires_python}"
            )

    # Validate platforms has entries for all architectures
    for arch in layer_config["architectures"]:
        if arch not in layer_config["platforms"]:
            errors.append(
                f"{layer_name}: Missing platform mapping for architecture '{arch}'"
            )

    return errors


def get_platform(layer_dir: Path, arch: str) -> str:
    """Get platform string for architecture.

    Args:
        layer_dir: Path to the layer directory
        arch: Architecture name (e.g., 'x86_64', 'arm64')

    Returns:
        Platform string (e.g., 'manylinux2014_x86_64')

    Raises:
        KeyError: If architecture not found in platforms mapping
    """
    config = load_config(layer_dir)
    return config["tool"]["lambda_layer"]["platforms"][arch]


def get_build_matrix(layer_dir: Path) -> list[dict]:
    """Get build matrix from layer config.

    Args:
        layer_dir: Path to the layer directory

    Returns:
        List of build variant dictionaries with python, arch, and platform keys
    """
    config = load_config(layer_dir)
    layer_config = config["tool"]["lambda_layer"]

    matrix = []
    for py in layer_config["python_versions"]:
        for arch in layer_config["architectures"]:
            matrix.append(
                {
                    "python": py,
                    "arch": arch,
                    "platform": layer_config["platforms"][arch],
                }
            )
    return matrix


def get_version(layer_dir: Path) -> str:
    """Get version from pyproject.toml.

    Args:
        layer_dir: Path to the layer directory

    Returns:
        Version string from [project] section
    """
    config = load_config(layer_dir)
    return config["project"]["version"]


def check_version_exists(layer_dir: Path, bucket: str, prefix: str = "layers") -> bool:
    """Check if any artifact exists for this layer version in S3.

    Args:
        layer_dir: Path to layer directory
        bucket: S3 bucket name
        prefix: S3 prefix (default: "layers")

    Returns:
        True if any artifact exists, False otherwise
    """
    version = get_version(layer_dir)
    layer_name = layer_dir.name
    s3_prefix = f"{prefix}/{layer_name}/{version}/"

    # Use AWS CLI to check if any objects exist
    result = subprocess.run(
        ["aws", "s3", "ls", f"s3://{bucket}/{s3_prefix}"],
        capture_output=True,
        text=True,
    )
    return result.returncode == 0 and result.stdout.strip() != ""


def main():
    """Main entry point for CLI."""
    parser = argparse.ArgumentParser(description="Validate layer configuration")
    parser.add_argument(
        "command",
        choices=["validate", "platform", "matrix", "version", "check-version"],
    )
    parser.add_argument("layer_dir", type=Path)
    parser.add_argument("--arch", help="Architecture for platform lookup")
    parser.add_argument("--python", help="Python version to validate")
    parser.add_argument("--bucket", help="S3 bucket name for version check")
    parser.add_argument(
        "--prefix",
        default="layers",
        help="S3 prefix for version check (default: layers)",
    )

    args = parser.parse_args()

    try:
        if args.command == "validate":
            config = load_config(args.layer_dir)
            errors = validate_config(config, args.layer_dir.name)
            if errors:
                for e in errors:
                    logger.error(e)
                sys.exit(1)
            logger.info("✓ Configuration valid")

        elif args.command == "platform":
            if not args.arch:
                logger.error("--arch required for platform lookup")
                sys.exit(1)
            print(get_platform(args.layer_dir, args.arch))

        elif args.command == "matrix":
            print(json.dumps({"include": get_build_matrix(args.layer_dir)}))

        elif args.command == "version":
            print(get_version(args.layer_dir))

        elif args.command == "check-version":
            if not args.bucket:
                logger.error("--bucket required for version check")
                sys.exit(1)

            version = get_version(args.layer_dir)
            layer_name = args.layer_dir.name

            if check_version_exists(args.layer_dir, args.bucket, args.prefix):
                logger.info(
                    f"Version {version} exists for layer '{layer_name}' in s3://{args.bucket}/{args.prefix}/"
                )
                sys.exit(0)
            else:
                logger.info(
                    f"Version {version} does not exist for layer '{layer_name}' in s3://{args.bucket}/{args.prefix}/"
                )
                sys.exit(1)

    except FileNotFoundError as e:
        logger.error(str(e))
        sys.exit(1)
    except KeyError as e:
        logger.error(f"Key not found: {e}")
        sys.exit(1)
    except Exception as e:
        logger.error(str(e))
        sys.exit(1)


if __name__ == "__main__":
    main()
