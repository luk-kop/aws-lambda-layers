#!/usr/bin/env python3
"""Layer configuration utilities.

Provides validation, extraction, and CI matrix building from pyproject.toml files.

CLI Usage:
    # Subcommands (from validate_config.py)
    layer_config.py validate <layer_dir>
    layer_config.py platform <layer_dir> --arch <arch>
    layer_config.py matrix <layer_dir>
    layer_config.py version <layer_dir>

    # Stdin mode (from build_matrix.py)
    git diff --name-only | grep '^layers/' | python layer_config.py

Public Functions:
    load_config(layer_dir: Path) -> dict
    validate_config(config: dict, layer_name: str) -> list[str]
    get_platform(layer_dir: Path, arch: str) -> str
    get_build_matrix(layer_dir: Path) -> list[dict]
    get_version(layer_dir: Path) -> str
    extract_layer_names(paths: list[str]) -> list[str]
    get_build_config(layer_dir: Path) -> dict
    build_output(layers: list[str]) -> dict
"""

import argparse
import json
import logging
import sys
import tomllib
from itertools import product
from pathlib import Path

from packaging.specifiers import SpecifierSet

# Configure logging with nice formatting
logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s: %(message)s",
)
logger = logging.getLogger(__name__)

# Directory containing all layer definitions
LAYERS_DIR = Path("layers")


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
    requires_python = config["project"].get("requires-python")
    if not requires_python:
        errors.append(
            f"{layer_name}: Missing 'requires-python' field in [project] section"
        )
        return errors
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


def extract_layer_names(paths: list[str]) -> list[str]:
    """Extract unique layer names from file paths.

    Args:
        paths: List of file paths (expected to start with 'layers/')

    Returns:
        Sorted list of unique layer names
    """
    layers = set()
    for path in paths:
        # Safety check: skip non-layer paths
        if not path.startswith("layers/"):
            continue
        parts = path.split("/")
        if len(parts) >= 2:
            layers.add(parts[1])
    return sorted(layers)


def get_build_config(layer_dir: Path) -> dict:
    """Get build configuration from layer's pyproject.toml.

    Args:
        layer_dir: Path to the layer directory containing pyproject.toml

    Returns:
        Dictionary with python_versions and architectures lists
    """
    pyproject = layer_dir / "pyproject.toml"
    with open(pyproject, "rb") as f:
        config = tomllib.load(f)

    lambda_layer = config.get("tool", {}).get("lambda_layer", {})
    return {
        "python_versions": lambda_layer.get("python_versions", ["3.12"]),
        "architectures": lambda_layer.get("architectures", ["x86_64"]),
    }


def build_output(layers: list[str]) -> dict:
    """Build the output JSON structure for CI consumption.

    Args:
        layers: List of layer names to include in the matrix

    Returns:
        Dictionary with layers, matrix, build_matrix, and has_changes fields.
        matrix and build_matrix are plain arrays (CI-agnostic).

    Raises:
        FileNotFoundError: If layer directory exists but missing required files
    """
    if not layers:
        return {
            "layers": [],
            "matrix": [],
            "build_matrix": [],
            "has_changes": False,
        }

    matrix = []
    build_matrix_items = []
    valid_layers = []

    for layer in layers:
        layer_dir = LAYERS_DIR / layer
        pyproject = layer_dir / "pyproject.toml"
        lockfile = layer_dir / "uv.lock"

        # Layer directory deleted entirely = skip with warning
        if not layer_dir.exists():
            logger.warning(f"Layer '{layer}' deleted, skipping")
            continue

        # Directory exists but missing required files = error
        if not pyproject.exists():
            raise FileNotFoundError(
                f"Layer '{layer}' exists but missing pyproject.toml"
            )

        if not lockfile.exists():
            raise FileNotFoundError(
                f"Layer '{layer}' exists but missing uv.lock. Run: cd layers/{layer} && uv lock"
            )

        version = get_version(layer_dir)
        valid_layers.append(layer)

        matrix.append({"name": layer, "version": version})

        build_config = get_build_config(layer_dir)
        for py, arch in product(
            build_config["python_versions"], build_config["architectures"]
        ):
            build_matrix_items.append(
                {"layer": layer, "version": version, "python": py, "arch": arch}
            )

    return {
        "layers": valid_layers,
        "matrix": matrix,
        "build_matrix": build_matrix_items,
        "has_changes": len(valid_layers) > 0,
    }


# =============================================================================
# CLI Implementation
# =============================================================================


def _run_subcommand() -> int:
    """Run in subcommand mode (validate, platform, matrix, version).

    Returns:
        Exit code (0 for success, 1 for error)
    """
    parser = argparse.ArgumentParser(
        description="Validate layer configuration and extract build information.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  %(prog)s validate layers/common
  %(prog)s platform layers/common --arch x86_64
  %(prog)s matrix layers/common
  %(prog)s version layers/common
""",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate layer pyproject.toml configuration",
        description="Validates [project] and [tool.lambda_layer] sections.",
    )
    validate_parser.add_argument("layer_dir", type=Path, help="Path to layer directory")

    # platform command
    platform_parser = subparsers.add_parser(
        "platform",
        help="Get platform string for an architecture",
        description="Returns the manylinux platform string for uv pip install.",
    )
    platform_parser.add_argument("layer_dir", type=Path, help="Path to layer directory")
    platform_parser.add_argument(
        "--arch",
        required=True,
        help="Architecture (x86_64 or arm64)",
    )

    # matrix command
    matrix_parser = subparsers.add_parser(
        "matrix",
        help="Output build matrix as JSON",
        description="Returns JSON with all python/arch combinations for CI.",
    )
    matrix_parser.add_argument("layer_dir", type=Path, help="Path to layer directory")

    # version command
    version_parser = subparsers.add_parser(
        "version",
        help="Get layer version from pyproject.toml",
        description="Returns the [project].version value.",
    )
    version_parser.add_argument("layer_dir", type=Path, help="Path to layer directory")

    args = parser.parse_args()

    try:
        if args.command == "validate":
            config = load_config(args.layer_dir)
            errors = validate_config(config, args.layer_dir.name)
            if errors:
                for e in errors:
                    logger.error(e)
                return 1
            logger.info("✓ Configuration valid")

        elif args.command == "platform":
            if not args.arch:
                logger.error("--arch required for platform lookup")
                return 1
            print(get_platform(args.layer_dir, args.arch))

        elif args.command == "matrix":
            print(json.dumps(get_build_matrix(args.layer_dir)))

        elif args.command == "version":
            print(get_version(args.layer_dir))

    except FileNotFoundError as e:
        logger.error(str(e))
        return 1
    except KeyError as e:
        logger.error(f"Key not found: {e}")
        return 1
    except Exception as e:
        logger.error(str(e))
        return 1

    return 0


def _run_stdin_mode() -> int:
    """Run in stdin mode (build matrix from paths).

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # Read paths from stdin
    input_text = sys.stdin.read().strip()
    paths = [p.strip() for p in input_text.split("\n") if p.strip()]

    try:
        layers = extract_layer_names(paths)
        output = build_output(layers)
        print(json.dumps(output))
        return 0
    except Exception as e:
        print(f"ERROR: {e}", file=sys.stderr)
        return 1


def main() -> int:
    """Main entry point for CLI.

    Detects mode based on:
    - If there are command line arguments (beyond script name) -> subcommand mode
    - If stdin is not a TTY (piped input) and no arguments -> stdin mode
    - If stdin is a TTY and no arguments -> subcommand mode (will show help)

    Returns:
        Exit code (0 for success, 1 for error)
    """
    # If we have arguments, use subcommand mode
    if len(sys.argv) > 1:
        return _run_subcommand()

    # If stdin is not a TTY (piped input), use stdin mode
    if not sys.stdin.isatty():
        return _run_stdin_mode()

    # No arguments and stdin is TTY -> show help via subcommand mode
    return _run_subcommand()


if __name__ == "__main__":
    sys.exit(main())
