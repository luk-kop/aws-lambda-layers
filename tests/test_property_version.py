#!/usr/bin/env python3
"""Property-based tests for version extraction.

This module contains property-based tests using hypothesis to verify
that version extraction returns the exact version string from pyproject.toml.

Feature: auto-detect-layer-release, Property 4: Version Extraction Round-Trip
"""

import sys
import tempfile
from pathlib import Path

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

get_version = validate_config_module.get_version


# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Strategy for valid X.Y version strings (as per product.md versioning strategy)
version_xy_strategy = st.builds(
    lambda major, minor: f"{major}.{minor}",
    major=st.integers(min_value=0, max_value=99),
    minor=st.integers(min_value=0, max_value=99),
)

# Strategy for valid X.Y.Z version strings (semver-like)
version_xyz_strategy = st.builds(
    lambda major, minor, patch: f"{major}.{minor}.{patch}",
    major=st.integers(min_value=0, max_value=99),
    minor=st.integers(min_value=0, max_value=99),
    patch=st.integers(min_value=0, max_value=99),
)

# Strategy for valid layer names (alphanumeric with hyphens)
layer_name_strategy = st.from_regex(r"[a-z][a-z0-9\-]{0,20}", fullmatch=True)

# Combined strategy for all valid version formats
version_strategy = st.one_of(
    version_xy_strategy,
    version_xyz_strategy,
)


def create_pyproject_toml(layer_dir: Path, layer_name: str, version: str) -> None:
    """Create a minimal valid pyproject.toml file.

    Args:
        layer_dir: Directory to create the file in
        layer_name: Name of the layer (must match directory name for validation)
        version: Version string to set
    """
    content = f'''[project]
name = "{layer_name}"
version = "{version}"
requires-python = ">=3.11"

[tool.lambda_layer]
python_versions = ["3.12"]
architectures = ["x86_64"]
platforms = {{ x86_64 = "manylinux2014_x86_64" }}
'''
    pyproject = layer_dir / "pyproject.toml"
    pyproject.write_text(content)


# =============================================================================
# Property-Based Tests
# =============================================================================


@pytest.mark.property
class TestVersionExtractionRoundTrip:
    """Property-based tests for version extraction round-trip.

    Feature: auto-detect-layer-release, Property 4: Version Extraction Round-Trip

    **Validates: Requirements 5.1**

    Property 4: For any valid pyproject.toml file with a [project].version field,
    the validate-config.py version command SHALL return the exact version string
    from the file.
    """

    @settings(max_examples=100)
    @given(version=version_xy_strategy)
    def test_version_extraction_xy_format(self, version: str):
        """Test that X.Y version strings are extracted exactly.

        **Validates: Requirements 5.1 (Property 4)**

        This property verifies that version strings in X.Y format
        (as per the product versioning strategy) are extracted exactly
        as written in pyproject.toml.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / "test-layer"
            layer_dir.mkdir()

            create_pyproject_toml(layer_dir, "test-layer", version)

            extracted_version = get_version(layer_dir)

            # Property: Extracted version must match exactly
            assert extracted_version == version, (
                f"Version extraction round-trip failed.\n"
                f"Input version: {version!r}\n"
                f"Extracted version: {extracted_version!r}"
            )

    @settings(max_examples=100)
    @given(version=version_xyz_strategy)
    def test_version_extraction_xyz_format(self, version: str):
        """Test that X.Y.Z version strings are extracted exactly.

        **Validates: Requirements 5.1 (Property 4)**

        This property verifies that version strings in X.Y.Z format
        (semver-like) are extracted exactly as written in pyproject.toml.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / "test-layer"
            layer_dir.mkdir()

            create_pyproject_toml(layer_dir, "test-layer", version)

            extracted_version = get_version(layer_dir)

            # Property: Extracted version must match exactly
            assert extracted_version == version, (
                f"Version extraction round-trip failed.\n"
                f"Input version: {version!r}\n"
                f"Extracted version: {extracted_version!r}"
            )

    @settings(max_examples=100)
    @given(version=version_strategy)
    def test_version_extraction_all_formats(self, version: str):
        """Test that all valid version formats are extracted exactly.

        **Validates: Requirements 5.1 (Property 4)**

        This property verifies that any valid version string format
        is extracted exactly as written in pyproject.toml.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / "test-layer"
            layer_dir.mkdir()

            create_pyproject_toml(layer_dir, "test-layer", version)

            extracted_version = get_version(layer_dir)

            # Property: Extracted version must match exactly
            assert extracted_version == version, (
                f"Version extraction round-trip failed.\n"
                f"Input version: {version!r}\n"
                f"Extracted version: {extracted_version!r}"
            )

    @settings(max_examples=100)
    @given(version=version_strategy, layer_name=layer_name_strategy)
    def test_version_extraction_independent_of_layer_name(self, version: str, layer_name: str):
        """Test that version extraction works regardless of layer name.

        **Validates: Requirements 5.1 (Property 4)**

        This property verifies that the version extraction is independent
        of the layer name - any valid layer name should work.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / layer_name
            layer_dir.mkdir()

            create_pyproject_toml(layer_dir, layer_name, version)

            extracted_version = get_version(layer_dir)

            # Property: Extracted version must match exactly
            assert extracted_version == version, (
                f"Version extraction round-trip failed for layer '{layer_name}'.\n"
                f"Input version: {version!r}\n"
                f"Extracted version: {extracted_version!r}"
            )

    @settings(max_examples=100)
    @given(version=version_strategy)
    def test_version_extraction_is_string_type(self, version: str):
        """Test that extracted version is always a string type.

        **Validates: Requirements 5.1 (Property 4)**

        This property verifies that the extracted version is always
        returned as a string, not converted to a number or other type.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / "test-layer"
            layer_dir.mkdir()

            create_pyproject_toml(layer_dir, "test-layer", version)

            extracted_version = get_version(layer_dir)

            # Property: Extracted version must be a string
            assert isinstance(extracted_version, str), (
                f"Extracted version should be string type.\n"
                f"Got type: {type(extracted_version).__name__}\n"
                f"Value: {extracted_version!r}"
            )


@pytest.mark.property
class TestVersionExtractionEdgeCases:
    """Edge case tests for version extraction.

    Feature: auto-detect-layer-release, Property 4: Version Extraction Round-Trip

    **Validates: Requirements 5.1**
    """

    @settings(max_examples=100)
    @given(
        major=st.integers(min_value=0, max_value=0), minor=st.integers(min_value=0, max_value=99)
    )
    def test_version_with_zero_major(self, major: int, minor: int):
        """Test that versions with zero major component are handled correctly.

        **Validates: Requirements 5.1 (Property 4)**

        Versions like "0.1", "0.99" should be extracted exactly.
        """
        version = f"{major}.{minor}"

        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / "test-layer"
            layer_dir.mkdir()

            create_pyproject_toml(layer_dir, "test-layer", version)

            extracted_version = get_version(layer_dir)

            # Property: Zero major versions should be preserved
            assert extracted_version == version, (
                f"Zero major version not preserved.\n"
                f"Input: {version!r}\n"
                f"Extracted: {extracted_version!r}"
            )

    @settings(max_examples=100)
    @given(
        major=st.integers(min_value=0, max_value=99), minor=st.integers(min_value=0, max_value=0)
    )
    def test_version_with_zero_minor(self, major: int, minor: int):
        """Test that versions with zero minor component are handled correctly.

        **Validates: Requirements 5.1 (Property 4)**

        Versions like "1.0", "99.0" should be extracted exactly.
        """
        version = f"{major}.{minor}"

        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / "test-layer"
            layer_dir.mkdir()

            create_pyproject_toml(layer_dir, "test-layer", version)

            extracted_version = get_version(layer_dir)

            # Property: Zero minor versions should be preserved
            assert extracted_version == version, (
                f"Zero minor version not preserved.\n"
                f"Input: {version!r}\n"
                f"Extracted: {extracted_version!r}"
            )

    @settings(max_examples=100)
    @given(
        major=st.integers(min_value=10, max_value=99), minor=st.integers(min_value=10, max_value=99)
    )
    def test_version_with_double_digit_components(self, major: int, minor: int):
        """Test that versions with double-digit components are handled correctly.

        **Validates: Requirements 5.1 (Property 4)**

        Versions like "10.20", "99.99" should be extracted exactly.
        """
        version = f"{major}.{minor}"

        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / "test-layer"
            layer_dir.mkdir()

            create_pyproject_toml(layer_dir, "test-layer", version)

            extracted_version = get_version(layer_dir)

            # Property: Double-digit versions should be preserved
            assert extracted_version == version, (
                f"Double-digit version not preserved.\n"
                f"Input: {version!r}\n"
                f"Extracted: {extracted_version!r}"
            )

    @settings(max_examples=100)
    @given(st.data())
    def test_version_0_0_edge_case(self, data):
        """Test that version "0.0" is handled correctly.

        **Validates: Requirements 5.1 (Property 4)**

        The minimum valid version "0.0" should be extracted exactly.
        """
        version = "0.0"

        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / "test-layer"
            layer_dir.mkdir()

            create_pyproject_toml(layer_dir, "test-layer", version)

            extracted_version = get_version(layer_dir)

            # Property: Minimum version should be preserved
            assert extracted_version == version, (
                f"Minimum version not preserved.\n"
                f"Input: {version!r}\n"
                f"Extracted: {extracted_version!r}"
            )


@pytest.mark.property
class TestVersionExtractionConsistency:
    """Consistency tests for version extraction.

    Feature: auto-detect-layer-release, Property 4: Version Extraction Round-Trip

    **Validates: Requirements 5.1**
    """

    @settings(max_examples=100)
    @given(version=version_strategy)
    def test_version_extraction_is_idempotent(self, version: str):
        """Test that multiple extractions return the same result.

        **Validates: Requirements 5.1 (Property 4)**

        Calling get_version multiple times on the same file should
        always return the same result.
        """
        with tempfile.TemporaryDirectory() as tmp_dir:
            layer_dir = Path(tmp_dir) / "test-layer"
            layer_dir.mkdir()

            create_pyproject_toml(layer_dir, "test-layer", version)

            # Extract version multiple times
            extracted_1 = get_version(layer_dir)
            extracted_2 = get_version(layer_dir)
            extracted_3 = get_version(layer_dir)

            # Property: All extractions should be identical
            assert extracted_1 == extracted_2 == extracted_3, (
                f"Version extraction is not idempotent.\n"
                f"First: {extracted_1!r}\n"
                f"Second: {extracted_2!r}\n"
                f"Third: {extracted_3!r}"
            )

    @settings(max_examples=100)
    @given(version1=version_strategy, version2=version_strategy)
    def test_different_versions_extracted_differently(self, version1: str, version2: str):
        """Test that different versions are extracted as different values.

        **Validates: Requirements 5.1 (Property 4)**

        If two pyproject.toml files have different versions, the extracted
        versions should also be different.
        """
        assume(version1 != version2)

        with tempfile.TemporaryDirectory() as tmp_dir:
            # Create two layer directories with different versions
            layer_dir1 = Path(tmp_dir) / "layer1"
            layer_dir1.mkdir()
            create_pyproject_toml(layer_dir1, "layer1", version1)

            layer_dir2 = Path(tmp_dir) / "layer2"
            layer_dir2.mkdir()
            create_pyproject_toml(layer_dir2, "layer2", version2)

            extracted_1 = get_version(layer_dir1)
            extracted_2 = get_version(layer_dir2)

            # Property: Different input versions should produce different outputs
            assert extracted_1 != extracted_2, (
                f"Different versions should be extracted differently.\n"
                f"Version 1: {version1!r} -> {extracted_1!r}\n"
                f"Version 2: {version2!r} -> {extracted_2!r}"
            )
