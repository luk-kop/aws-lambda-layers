#!/usr/bin/env python3
"""Property-based tests for build matrix generation.

This module contains property-based tests using hypothesis to verify
that the build matrix is exactly the Cartesian product of python_versions × architectures.

Feature: auto-detect-layer-release, Property 5: Build Matrix Generation
"""

import itertools
import sys
import tempfile
from pathlib import Path
from typing import Callable

import pytest
from hypothesis import assume, given, settings
from hypothesis import strategies as st

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

# Load validate-config.py as a module
from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader

script_path = Path(__file__).parent.parent / "scripts" / "validate-config.py"
loader = SourceFileLoader("validate_config", str(script_path))
spec = spec_from_loader("validate_config", loader)
validate_config_module = module_from_spec(spec)
loader.exec_module(validate_config_module)

get_build_matrix = validate_config_module.get_build_matrix


# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Strategy for valid Python versions (supported by Lambda: 3.11, 3.12)
VALID_PYTHON_VERSIONS = ["3.11", "3.12"]
python_version_strategy = st.sampled_from(VALID_PYTHON_VERSIONS)

# Strategy for non-empty subsets of Python versions
python_versions_list_strategy = st.lists(
    python_version_strategy,
    min_size=1,
    max_size=len(VALID_PYTHON_VERSIONS),
    unique=True,
)

# Strategy for valid architectures (supported by Lambda)
VALID_ARCHITECTURES = ["x86_64", "arm64"]
arch_strategy = st.sampled_from(VALID_ARCHITECTURES)

# Strategy for non-empty subsets of architectures
architectures_list_strategy = st.lists(
    arch_strategy, min_size=1, max_size=len(VALID_ARCHITECTURES), unique=True
)

# Strategy for valid layer names
layer_name_strategy = st.from_regex(r"[a-z][a-z0-9\-]{0,20}", fullmatch=True)

# Strategy for valid version strings (X.Y format)
version_strategy = st.builds(
    lambda major, minor: f"{major}.{minor}",
    major=st.integers(min_value=0, max_value=99),
    minor=st.integers(min_value=0, max_value=99),
)

# Platform mappings for architectures
PLATFORM_MAPPINGS = {"x86_64": "manylinux2014_x86_64", "arm64": "manylinux2014_aarch64"}


def create_pyproject_toml(
    layer_dir: Path,
    layer_name: str,
    version: str,
    python_versions: list[str],
    architectures: list[str],
) -> None:
    """Create a valid pyproject.toml file with lambda_layer configuration.

    Args:
        layer_dir: Directory to create the file in
        layer_name: Name of the layer (must match directory name for validation)
        version: Version string to set
        python_versions: List of Python versions (e.g., ["3.11", "3.12"])
        architectures: List of architectures (e.g., ["x86_64", "arm64"])
    """
    # Build the python_versions list string
    py_versions_str = ", ".join(f'"{v}"' for v in python_versions)

    # Build the architectures list string
    arch_str = ", ".join(f'"{a}"' for a in architectures)

    # Build the platforms mapping string
    platforms_entries = []
    for arch in architectures:
        platforms_entries.append(f'{arch} = "{PLATFORM_MAPPINGS[arch]}"')
    platforms_str = ", ".join(platforms_entries)

    content = f'''[project]
name = "{layer_name}"
version = "{version}"
requires-python = ">=3.11"

[tool.lambda_layer]
python_versions = [{py_versions_str}]
architectures = [{arch_str}]
platforms = {{ {platforms_str} }}
'''
    pyproject = layer_dir / "pyproject.toml"
    pyproject.write_text(content)


@st.composite
def matrix_config_strategy(draw: Callable) -> dict:
    """Generate valid configuration for build matrix testing.

    Returns:
        Dictionary with layer_name, version, python_versions, and architectures
    """
    return {
        "layer_name": draw(layer_name_strategy),
        "version": draw(version_strategy),
        "python_versions": draw(python_versions_list_strategy),
        "architectures": draw(architectures_list_strategy),
    }


# =============================================================================
# Property-Based Tests
# =============================================================================


@pytest.mark.property
class TestBuildMatrixGeneration:
    """Property-based tests for build matrix generation.

    Feature: auto-detect-layer-release, Property 5: Build Matrix Generation

    **Validates: Requirements 5.2**

    Property 5: For any valid pyproject.toml with [tool.lambda_layer] configuration,
    the generated build matrix SHALL contain exactly the Cartesian product of
    python_versions × architectures.
    """

    @settings(max_examples=100)
    @given(config=matrix_config_strategy())
    def test_matrix_size_is_cartesian_product(self, config: dict):
        """Test that matrix size equals len(python_versions) × len(architectures).

        **Validates: Requirements 5.2 (Property 5)**

        This property verifies that the number of entries in the build matrix
        is exactly the product of the number of Python versions and architectures.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / config["layer_name"]
            layer_dir.mkdir()

            create_pyproject_toml(
                layer_dir,
                config["layer_name"],
                config["version"],
                config["python_versions"],
                config["architectures"],
            )

            matrix = get_build_matrix(layer_dir)

            expected_size = len(config["python_versions"]) * len(
                config["architectures"]
            )

            # Property: Matrix size must equal Cartesian product size
            assert len(matrix) == expected_size, (
                f"Matrix size mismatch.\n"
                f"Python versions: {config['python_versions']} "
                f"(count: {len(config['python_versions'])})\n"
                f"Architectures: {config['architectures']} "
                f"(count: {len(config['architectures'])})\n"
                f"Expected matrix size: {expected_size}\n"
                f"Actual matrix size: {len(matrix)}"
            )

    @settings(max_examples=100)
    @given(config=matrix_config_strategy())
    def test_matrix_contains_all_combinations(self, config: dict):
        """Test that matrix contains every combination of python × arch.

        **Validates: Requirements 5.2 (Property 5)**

        This property verifies that every possible combination of Python version
        and architecture appears exactly once in the build matrix.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / config["layer_name"]
            layer_dir.mkdir()

            create_pyproject_toml(
                layer_dir,
                config["layer_name"],
                config["version"],
                config["python_versions"],
                config["architectures"],
            )

            matrix = get_build_matrix(layer_dir)

            # Generate expected Cartesian product
            expected_combinations = set(
                itertools.product(config["python_versions"], config["architectures"])
            )

            # Extract actual combinations from matrix
            actual_combinations = set(
                (entry["python"], entry["arch"]) for entry in matrix
            )

            # Property: Actual combinations must match expected Cartesian product
            assert actual_combinations == expected_combinations, (
                f"Matrix combinations mismatch.\n"
                f"Expected: {expected_combinations}\n"
                f"Actual: {actual_combinations}\n"
                f"Missing: {expected_combinations - actual_combinations}\n"
                f"Extra: {actual_combinations - expected_combinations}"
            )

    @settings(max_examples=100)
    @given(config=matrix_config_strategy())
    def test_matrix_entries_have_required_keys(self, config: dict):
        """Test that each matrix entry has python, arch, and platform keys.

        **Validates: Requirements 5.2 (Property 5)**

        This property verifies that each entry in the build matrix contains
        all required keys for building a layer variant.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / config["layer_name"]
            layer_dir.mkdir()

            create_pyproject_toml(
                layer_dir,
                config["layer_name"],
                config["version"],
                config["python_versions"],
                config["architectures"],
            )

            matrix = get_build_matrix(layer_dir)

            required_keys = {"python", "arch", "platform"}

            for i, entry in enumerate(matrix):
                # Property: Each entry must have all required keys
                assert set(entry.keys()) == required_keys, (
                    f"Matrix entry {i} has incorrect keys.\n"
                    f"Expected keys: {required_keys}\n"
                    f"Actual keys: {set(entry.keys())}\n"
                    f"Entry: {entry}"
                )

    @settings(max_examples=100)
    @given(config=matrix_config_strategy())
    def test_matrix_platforms_are_correct(self, config: dict):
        """Test that platform values match the architecture mappings.

        **Validates: Requirements 5.2 (Property 5)**

        This property verifies that each matrix entry has the correct platform
        string for its architecture (x86_64 → manylinux2014_x86_64,
        arm64 → manylinux2014_aarch64).
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / config["layer_name"]
            layer_dir.mkdir()

            create_pyproject_toml(
                layer_dir,
                config["layer_name"],
                config["version"],
                config["python_versions"],
                config["architectures"],
            )

            matrix = get_build_matrix(layer_dir)

            for entry in matrix:
                expected_platform = PLATFORM_MAPPINGS[entry["arch"]]

                # Property: Platform must match architecture mapping
                assert entry["platform"] == expected_platform, (
                    f"Platform mismatch for architecture '{entry['arch']}'.\n"
                    f"Expected platform: {expected_platform}\n"
                    f"Actual platform: {entry['platform']}"
                )

    @settings(max_examples=100)
    @given(config=matrix_config_strategy())
    def test_matrix_has_no_duplicates(self, config: dict):
        """Test that matrix contains no duplicate entries.

        **Validates: Requirements 5.2 (Property 5)**

        This property verifies that each (python, arch) combination appears
        exactly once in the build matrix.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / config["layer_name"]
            layer_dir.mkdir()

            create_pyproject_toml(
                layer_dir,
                config["layer_name"],
                config["version"],
                config["python_versions"],
                config["architectures"],
            )

            matrix = get_build_matrix(layer_dir)

            # Extract (python, arch) tuples
            combinations = [(entry["python"], entry["arch"]) for entry in matrix]

            # Property: No duplicates should exist
            assert len(combinations) == len(set(combinations)), (
                f"Matrix contains duplicate entries.\n"
                f"Total entries: {len(combinations)}\n"
                f"Unique entries: {len(set(combinations))}\n"
                f"Combinations: {combinations}"
            )


@pytest.mark.property
class TestBuildMatrixSpecificCases:
    """Property-based tests for specific build matrix scenarios.

    Feature: auto-detect-layer-release, Property 5: Build Matrix Generation

    **Validates: Requirements 5.2**
    """

    @settings(max_examples=100)
    @given(layer_name=layer_name_strategy, version=version_strategy)
    def test_single_python_single_arch_produces_one_entry(
        self, layer_name: str, version: str
    ):
        """Test that single python × single arch produces exactly 1 entry.

        **Validates: Requirements 5.2 (Property 5)**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / layer_name
            layer_dir.mkdir()

            create_pyproject_toml(
                layer_dir,
                layer_name,
                version,
                python_versions=["3.12"],
                architectures=["x86_64"],
            )

            matrix = get_build_matrix(layer_dir)

            # Property: 1 × 1 = 1 entry
            assert len(matrix) == 1, (
                f"Expected 1 entry for single python × single arch, got {len(matrix)}"
            )
            assert matrix[0]["python"] == "3.12"
            assert matrix[0]["arch"] == "x86_64"

    @settings(max_examples=100)
    @given(layer_name=layer_name_strategy, version=version_strategy)
    def test_two_python_two_arch_produces_four_entries(
        self, layer_name: str, version: str
    ):
        """Test that 2 python × 2 arch produces exactly 4 entries.

        **Validates: Requirements 5.2 (Property 5)**

        This matches the example from the design document:
        - Input: python_versions: ["3.11", "3.12"], architectures: ["x86_64", "arm64"]
        - Output matrix: 4 entries (3.11×x86_64, 3.11×arm64, 3.12×x86_64, 3.12×arm64)
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / layer_name
            layer_dir.mkdir()

            create_pyproject_toml(
                layer_dir,
                layer_name,
                version,
                python_versions=["3.11", "3.12"],
                architectures=["x86_64", "arm64"],
            )

            matrix = get_build_matrix(layer_dir)

            # Property: 2 × 2 = 4 entries
            assert len(matrix) == 4, (
                f"Expected 4 entries for 2 python × 2 arch, got {len(matrix)}"
            )

            # Verify all expected combinations exist
            expected = {
                ("3.11", "x86_64"),
                ("3.11", "arm64"),
                ("3.12", "x86_64"),
                ("3.12", "arm64"),
            }
            actual = {(e["python"], e["arch"]) for e in matrix}

            assert actual == expected, (
                f"Matrix combinations mismatch.\nExpected: {expected}\nActual: {actual}"
            )

    @settings(max_examples=100)
    @given(layer_name=layer_name_strategy, version=version_strategy)
    def test_single_python_two_arch_produces_two_entries(
        self, layer_name: str, version: str
    ):
        """Test that 1 python × 2 arch produces exactly 2 entries.

        **Validates: Requirements 5.2 (Property 5)**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / layer_name
            layer_dir.mkdir()

            create_pyproject_toml(
                layer_dir,
                layer_name,
                version,
                python_versions=["3.12"],
                architectures=["x86_64", "arm64"],
            )

            matrix = get_build_matrix(layer_dir)

            # Property: 1 × 2 = 2 entries
            assert len(matrix) == 2, (
                f"Expected 2 entries for 1 python × 2 arch, got {len(matrix)}"
            )

            # Verify combinations
            expected = {("3.12", "x86_64"), ("3.12", "arm64")}
            actual = {(e["python"], e["arch"]) for e in matrix}

            assert actual == expected

    @settings(max_examples=100)
    @given(layer_name=layer_name_strategy, version=version_strategy)
    def test_two_python_single_arch_produces_two_entries(
        self, layer_name: str, version: str
    ):
        """Test that 2 python × 1 arch produces exactly 2 entries.

        **Validates: Requirements 5.2 (Property 5)**
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / layer_name
            layer_dir.mkdir()

            create_pyproject_toml(
                layer_dir,
                layer_name,
                version,
                python_versions=["3.11", "3.12"],
                architectures=["x86_64"],
            )

            matrix = get_build_matrix(layer_dir)

            # Property: 2 × 1 = 2 entries
            assert len(matrix) == 2, (
                f"Expected 2 entries for 2 python × 1 arch, got {len(matrix)}"
            )

            # Verify combinations
            expected = {("3.11", "x86_64"), ("3.12", "x86_64")}
            actual = {(e["python"], e["arch"]) for e in matrix}

            assert actual == expected


@pytest.mark.property
class TestBuildMatrixConsistency:
    """Consistency tests for build matrix generation.

    Feature: auto-detect-layer-release, Property 5: Build Matrix Generation

    **Validates: Requirements 5.2**
    """

    @settings(max_examples=100)
    @given(config=matrix_config_strategy())
    def test_matrix_generation_is_deterministic(self, config: dict):
        """Test that multiple calls produce the same matrix.

        **Validates: Requirements 5.2 (Property 5)**

        Calling get_build_matrix multiple times on the same configuration
        should always return the same result.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / config["layer_name"]
            layer_dir.mkdir()

            create_pyproject_toml(
                layer_dir,
                config["layer_name"],
                config["version"],
                config["python_versions"],
                config["architectures"],
            )

            # Generate matrix multiple times
            matrix1 = get_build_matrix(layer_dir)
            matrix2 = get_build_matrix(layer_dir)
            matrix3 = get_build_matrix(layer_dir)

            # Property: All generations should be identical
            assert matrix1 == matrix2 == matrix3, (
                f"Matrix generation is not deterministic.\n"
                f"First: {matrix1}\n"
                f"Second: {matrix2}\n"
                f"Third: {matrix3}"
            )

    @settings(max_examples=100)
    @given(config1=matrix_config_strategy(), config2=matrix_config_strategy())
    def test_different_configs_produce_different_matrices(
        self, config1: dict, config2: dict
    ):
        """Test that different configurations produce different matrices.

        **Validates: Requirements 5.2 (Property 5)**

        If two configurations have different python_versions or architectures,
        their matrices should differ (unless they happen to be equivalent).
        """
        # Only test when configs are actually different
        assume(
            set(config1["python_versions"]) != set(config2["python_versions"])
            or set(config1["architectures"]) != set(config2["architectures"])
        )

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create first layer
            layer_dir1 = Path(tmp_dir) / "layer1"
            layer_dir1.mkdir()
            create_pyproject_toml(
                layer_dir1,
                "layer1",
                config1["version"],
                config1["python_versions"],
                config1["architectures"],
            )

            # Create second layer
            layer_dir2 = Path(tmp_dir) / "layer2"
            layer_dir2.mkdir()
            create_pyproject_toml(
                layer_dir2,
                "layer2",
                config2["version"],
                config2["python_versions"],
                config2["architectures"],
            )

            matrix1 = get_build_matrix(layer_dir1)
            matrix2 = get_build_matrix(layer_dir2)

            # Extract combinations for comparison
            combos1 = {(e["python"], e["arch"]) for e in matrix1}
            combos2 = {(e["python"], e["arch"]) for e in matrix2}

            # Property: Different configs should produce different combinations
            assert combos1 != combos2, (
                f"Different configs produced same matrix combinations.\n"
                f"Config 1: py={config1['python_versions']}, arch={config1['architectures']}\n"
                f"Config 2: py={config2['python_versions']}, arch={config2['architectures']}\n"
                f"Both produced: {combos1}"
            )

    @settings(max_examples=100)
    @given(config=matrix_config_strategy())
    def test_matrix_independent_of_version(self, config: dict):
        """Test that matrix is independent of the layer version.

        **Validates: Requirements 5.2 (Property 5)**

        The build matrix should only depend on python_versions and architectures,
        not on the layer version.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create layer with version 1.0
            layer_dir1 = Path(tmp_dir) / "layer1"
            layer_dir1.mkdir()
            create_pyproject_toml(
                layer_dir1,
                "layer1",
                "1.0",
                config["python_versions"],
                config["architectures"],
            )

            # Create layer with version 99.99
            layer_dir2 = Path(tmp_dir) / "layer2"
            layer_dir2.mkdir()
            create_pyproject_toml(
                layer_dir2,
                "layer2",
                "99.99",
                config["python_versions"],
                config["architectures"],
            )

            matrix1 = get_build_matrix(layer_dir1)
            matrix2 = get_build_matrix(layer_dir2)

            # Extract combinations (ignoring order)
            combos1 = {(e["python"], e["arch"], e["platform"]) for e in matrix1}
            combos2 = {(e["python"], e["arch"], e["platform"]) for e in matrix2}

            # Property: Matrices should be equivalent regardless of version
            assert combos1 == combos2, (
                f"Matrix depends on version.\n"
                f"Version 1.0 matrix: {combos1}\n"
                f"Version 99.99 matrix: {combos2}"
            )
