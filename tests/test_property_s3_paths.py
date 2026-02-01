#!/usr/bin/env python3
"""Property-based tests for S3 path formatting.

This module contains property-based tests using hypothesis to verify
that S3 paths are correctly formatted for both release and test prefixes.

Feature: auto-detect-layer-release, Property 3: S3 Path Formatting
"""

import re
from typing import Callable

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# =============================================================================
# S3 Path Formatting Logic (Pure Python implementation for testing)
# =============================================================================


def format_release_s3_path(
    layer_name: str, version: str, python_version: str, arch: str
) -> str:
    """Format S3 path for release artifacts.

    This is a pure Python implementation of the S3 path formatting logic
    used in upload-layer.sh for release artifacts.

    Args:
        layer_name: Name of the layer (e.g., 'common')
        version: Version string (e.g., '1.0')
        python_version: Python version without dots (e.g., '312')
        arch: Architecture (e.g., 'x86_64', 'arm64')

    Returns:
        S3 path in format: layers/<name>/<version>/py<python>-<arch>.zip
    """
    return f"layers/{layer_name}/{version}/py{python_version}-{arch}.zip"


def format_test_s3_path(
    pr_number: int, layer_name: str, version: str, python_version: str, arch: str
) -> str:
    """Format S3 path for test artifacts (PR builds).

    This is a pure Python implementation of the S3 path formatting logic
    used in upload-layer.sh for test artifacts.

    Args:
        pr_number: Pull request number
        layer_name: Name of the layer (e.g., 'common')
        version: Version string (e.g., '1.0')
        python_version: Python version without dots (e.g., '312')
        arch: Architecture (e.g., 'x86_64', 'arm64')

    Returns:
        S3 path in format: test/<pr-number>/<name>/<version>/py<python>-<arch>.zip
    """
    return f"test/{pr_number}/{layer_name}/{version}/py{python_version}-{arch}.zip"


def format_artifact_filename(python_version: str, arch: str) -> str:
    """Format the artifact filename.

    Args:
        python_version: Python version without dots (e.g., '312')
        arch: Architecture (e.g., 'x86_64', 'arm64')

    Returns:
        Filename in format: py<python>-<arch>.zip
    """
    return f"py{python_version}-{arch}.zip"


# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Strategy for valid layer names (alphanumeric with hyphens, like "common", "my-utils")
layer_name_strategy = st.from_regex(r"[a-z][a-z0-9\-]{0,20}", fullmatch=True)

# Strategy for valid version strings (X.Y format)
version_strategy = st.from_regex(r"[0-9]+\.[0-9]+", fullmatch=True)

# Strategy for supported Python versions (as they appear in filenames, without dots)
python_version_strategy = st.sampled_from(["311", "312"])

# Strategy for supported architectures
arch_strategy = st.sampled_from(["x86_64", "arm64"])

# Strategy for valid PR numbers (positive integers)
pr_number_strategy = st.integers(min_value=1, max_value=999999)


@st.composite
def release_path_components_strategy(draw: Callable) -> dict:
    """Generate valid components for a release S3 path.

    Returns:
        Dictionary with layer_name, version, python_version, and arch
    """
    return {
        "layer_name": draw(layer_name_strategy),
        "version": draw(version_strategy),
        "python_version": draw(python_version_strategy),
        "arch": draw(arch_strategy),
    }


@st.composite
def pr_path_components_strategy(draw: Callable) -> dict:
    """Generate valid components for a test/PR S3 path.

    Returns:
        Dictionary with pr_number, layer_name, version, python_version, and arch
    """
    return {
        "pr_number": draw(pr_number_strategy),
        "layer_name": draw(layer_name_strategy),
        "version": draw(version_strategy),
        "python_version": draw(python_version_strategy),
        "arch": draw(arch_strategy),
    }


# =============================================================================
# Property-Based Tests
# =============================================================================


@pytest.mark.property
class TestS3PathFormatting:
    """Property-based tests for S3 path formatting.

    Feature: auto-detect-layer-release, Property 3: S3 Path Formatting

    **Validates: Requirements 4.3, 6.1**

    Property 3: For any valid layer name, version, Python version, and architecture,
    the S3 path SHALL be formatted as:
    - Release: `layers/<name>/<version>/py<python>-<arch>.zip`
    - Test: `test/<pr-number>/<name>/<version>/py<python>-<arch>.zip`
    """

    @settings(max_examples=100)
    @given(components=release_path_components_strategy())
    def test_release_path_starts_with_layers_prefix(self, components: dict):
        """Test that release paths always start with 'layers/' prefix.

        **Validates: Requirements 6.1 (Property 3)**
        """
        path = format_release_s3_path(**components)

        # Property: Release paths must start with "layers/"
        assert path.startswith("layers/"), (
            f"Release path should start with 'layers/', got: {path}"
        )

    @settings(max_examples=100)
    @given(components=release_path_components_strategy())
    def test_release_path_ends_with_zip(self, components: dict):
        """Test that release paths always end with '.zip' extension.

        **Validates: Requirements 6.1 (Property 3)**
        """
        path = format_release_s3_path(**components)

        # Property: Release paths must end with ".zip"
        assert path.endswith(".zip"), (
            f"Release path should end with '.zip', got: {path}"
        )

    @settings(max_examples=100)
    @given(components=release_path_components_strategy())
    def test_release_path_contains_layer_name(self, components: dict):
        """Test that release paths contain the layer name.

        **Validates: Requirements 6.1 (Property 3)**
        """
        path = format_release_s3_path(**components)

        # Property: Path should contain the layer name
        assert f"/{components['layer_name']}/" in path, (
            f"Release path should contain layer name '{components['layer_name']}', got: {path}"
        )

    @settings(max_examples=100)
    @given(components=release_path_components_strategy())
    def test_release_path_contains_version(self, components: dict):
        """Test that release paths contain the version.

        **Validates: Requirements 6.1 (Property 3)**
        """
        path = format_release_s3_path(**components)

        # Property: Path should contain the version
        assert f"/{components['version']}/" in path, (
            f"Release path should contain version '{components['version']}', got: {path}"
        )

    @settings(max_examples=100)
    @given(components=release_path_components_strategy())
    def test_release_path_format_exact(self, components: dict):
        """Test that release paths match the exact expected format.

        **Validates: Requirements 6.1 (Property 3)**

        Expected format: layers/<name>/<version>/py<python>-<arch>.zip
        """
        path = format_release_s3_path(**components)

        expected = (
            f"layers/{components['layer_name']}/{components['version']}/"
            f"py{components['python_version']}-{components['arch']}.zip"
        )

        # Property: Path should match exact expected format
        assert path == expected, (
            f"Release path format mismatch.\nExpected: {expected}\nGot: {path}"
        )

    @settings(max_examples=100)
    @given(components=pr_path_components_strategy())
    def test_test_path_starts_with_test_prefix(self, components: dict):
        """Test that test paths always start with 'test/' prefix.

        **Validates: Requirements 4.3 (Property 3)**
        """
        path = format_test_s3_path(**components)

        # Property: Test paths must start with "test/"
        assert path.startswith("test/"), (
            f"Test path should start with 'test/', got: {path}"
        )

    @settings(max_examples=100)
    @given(components=pr_path_components_strategy())
    def test_test_path_ends_with_zip(self, components: dict):
        """Test that test paths always end with '.zip' extension.

        **Validates: Requirements 4.3 (Property 3)**
        """
        path = format_test_s3_path(**components)

        # Property: Test paths must end with ".zip"
        assert path.endswith(".zip"), f"Test path should end with '.zip', got: {path}"

    @settings(max_examples=100)
    @given(components=pr_path_components_strategy())
    def test_test_path_contains_pr_number(self, components: dict):
        """Test that test paths contain the PR number.

        **Validates: Requirements 4.3 (Property 3)**
        """
        path = format_test_s3_path(**components)

        # Property: Path should contain the PR number after "test/"
        assert f"test/{components['pr_number']}/" in path, (
            f"Test path should contain PR number '{components['pr_number']}', got: {path}"
        )

    @settings(max_examples=100)
    @given(components=pr_path_components_strategy())
    def test_test_path_contains_layer_name(self, components: dict):
        """Test that test paths contain the layer name.

        **Validates: Requirements 4.3 (Property 3)**
        """
        path = format_test_s3_path(**components)

        # Property: Path should contain the layer name
        assert f"/{components['layer_name']}/" in path, (
            f"Test path should contain layer name '{components['layer_name']}', got: {path}"
        )

    @settings(max_examples=100)
    @given(components=pr_path_components_strategy())
    def test_test_path_format_exact(self, components: dict):
        """Test that test paths match the exact expected format.

        **Validates: Requirements 4.3 (Property 3)**

        Expected format: test/<pr-number>/<name>/<version>/py<python>-<arch>.zip
        """
        path = format_test_s3_path(**components)

        expected = (
            f"test/{components['pr_number']}/{components['layer_name']}/"
            f"{components['version']}/py{components['python_version']}-{components['arch']}.zip"
        )

        # Property: Path should match exact expected format
        assert path == expected, (
            f"Test path format mismatch.\nExpected: {expected}\nGot: {path}"
        )


@pytest.mark.property
class TestS3PathStructure:
    """Property-based tests for S3 path structure invariants.

    Feature: auto-detect-layer-release, Property 3: S3 Path Formatting

    **Validates: Requirements 4.3, 6.1**
    """

    @settings(max_examples=100)
    @given(components=release_path_components_strategy())
    def test_release_path_has_four_segments(self, components: dict):
        """Test that release paths have exactly 4 path segments.

        **Validates: Requirements 6.1 (Property 3)**

        Format: layers/<name>/<version>/<filename>
        """
        path = format_release_s3_path(**components)
        segments = path.split("/")

        # Property: Release path should have exactly 4 segments
        assert len(segments) == 4, (
            f"Release path should have 4 segments, got {len(segments)}: {segments}"
        )

        # Verify segment positions
        assert segments[0] == "layers", (
            f"First segment should be 'layers', got: {segments[0]}"
        )
        assert segments[1] == components["layer_name"], (
            f"Second segment should be layer name, got: {segments[1]}"
        )
        assert segments[2] == components["version"], (
            f"Third segment should be version, got: {segments[2]}"
        )

    @settings(max_examples=100)
    @given(components=pr_path_components_strategy())
    def test_test_path_has_five_segments(self, components: dict):
        """Test that test paths have exactly 5 path segments.

        **Validates: Requirements 4.3 (Property 3)**

        Format: test/<pr-number>/<name>/<version>/<filename>
        """
        path = format_test_s3_path(**components)
        segments = path.split("/")

        # Property: Test path should have exactly 5 segments
        assert len(segments) == 5, (
            f"Test path should have 5 segments, got {len(segments)}: {segments}"
        )

        # Verify segment positions
        assert segments[0] == "test", (
            f"First segment should be 'test', got: {segments[0]}"
        )
        assert segments[1] == str(components["pr_number"]), (
            f"Second segment should be PR number, got: {segments[1]}"
        )
        assert segments[2] == components["layer_name"], (
            f"Third segment should be layer name, got: {segments[2]}"
        )
        assert segments[3] == components["version"], (
            f"Fourth segment should be version, got: {segments[3]}"
        )

    @settings(max_examples=100)
    @given(python_version=python_version_strategy, arch=arch_strategy)
    def test_artifact_filename_format(self, python_version: str, arch: str):
        """Test that artifact filenames follow the expected format.

        **Validates: Requirements 4.3, 6.1 (Property 3)**

        Expected format: py<python>-<arch>.zip
        """
        filename = format_artifact_filename(python_version, arch)

        # Property: Filename should match pattern py<python>-<arch>.zip
        pattern = r"^py\d{3}-(?:x86_64|arm64)\.zip$"
        assert re.match(pattern, filename), (
            f"Filename should match pattern 'py<python>-<arch>.zip', got: {filename}"
        )

        # Property: Filename should contain the python version
        assert f"py{python_version}" in filename, (
            f"Filename should contain python version, got: {filename}"
        )

        # Property: Filename should contain the architecture
        assert arch in filename, (
            f"Filename should contain architecture, got: {filename}"
        )


@pytest.mark.property
class TestS3PathConsistency:
    """Property-based tests for S3 path consistency between release and test.

    Feature: auto-detect-layer-release, Property 3: S3 Path Formatting

    **Validates: Requirements 4.3, 6.1**
    """

    @settings(max_examples=100)
    @given(
        layer_name=layer_name_strategy,
        version=version_strategy,
        python_version=python_version_strategy,
        arch=arch_strategy,
        pr_number=pr_number_strategy,
    )
    def test_release_and_test_share_same_filename(
        self,
        layer_name: str,
        version: str,
        python_version: str,
        arch: str,
        pr_number: int,
    ):
        """Test that release and test paths use the same filename format.

        **Validates: Requirements 4.3, 6.1 (Property 3)**

        Both release and test paths should end with the same filename
        (py<python>-<arch>.zip) for the same layer variant.
        """
        release_path = format_release_s3_path(layer_name, version, python_version, arch)
        test_path = format_test_s3_path(
            pr_number, layer_name, version, python_version, arch
        )

        release_filename = release_path.split("/")[-1]
        test_filename = test_path.split("/")[-1]

        # Property: Both paths should have the same filename
        assert release_filename == test_filename, (
            f"Release and test paths should have same filename.\n"
            f"Release: {release_filename}\n"
            f"Test: {test_filename}"
        )

    @settings(max_examples=100)
    @given(
        layer_name=layer_name_strategy,
        version=version_strategy,
        python_version=python_version_strategy,
        arch=arch_strategy,
        pr_number=pr_number_strategy,
    )
    def test_release_and_test_differ_only_in_prefix(
        self,
        layer_name: str,
        version: str,
        python_version: str,
        arch: str,
        pr_number: int,
    ):
        """Test that release and test paths differ only in their prefix.

        **Validates: Requirements 4.3, 6.1 (Property 3)**

        The common suffix (<name>/<version>/<filename>) should be identical.
        """
        release_path = format_release_s3_path(layer_name, version, python_version, arch)
        test_path = format_test_s3_path(
            pr_number, layer_name, version, python_version, arch
        )

        # Extract common suffix (everything after the prefix)
        release_suffix = "/".join(release_path.split("/")[1:])  # Remove "layers"
        test_suffix = "/".join(test_path.split("/")[2:])  # Remove "test/<pr>"

        # Property: Common suffix should be identical
        assert release_suffix == test_suffix, (
            f"Release and test paths should have same suffix.\n"
            f"Release suffix: {release_suffix}\n"
            f"Test suffix: {test_suffix}"
        )

    @settings(max_examples=100)
    @given(components=release_path_components_strategy())
    def test_release_path_no_double_slashes(self, components: dict):
        """Test that release paths never contain double slashes.

        **Validates: Requirements 6.1 (Property 3)**
        """
        path = format_release_s3_path(**components)

        # Property: Path should not contain double slashes
        assert "//" not in path, f"Path should not contain double slashes, got: {path}"

    @settings(max_examples=100)
    @given(components=pr_path_components_strategy())
    def test_test_path_no_double_slashes(self, components: dict):
        """Test that test paths never contain double slashes.

        **Validates: Requirements 4.3 (Property 3)**
        """
        path = format_test_s3_path(**components)

        # Property: Path should not contain double slashes
        assert "//" not in path, f"Path should not contain double slashes, got: {path}"


@pytest.mark.property
class TestS3PathEdgeCases:
    """Edge case tests for S3 path formatting.

    Feature: auto-detect-layer-release, Property 3: S3 Path Formatting

    **Validates: Requirements 4.3, 6.1**
    """

    @settings(max_examples=100)
    @given(
        layer_name=st.from_regex(r"[a-z]", fullmatch=True),  # Single char layer name
        version=version_strategy,
        python_version=python_version_strategy,
        arch=arch_strategy,
    )
    def test_single_char_layer_name(
        self, layer_name: str, version: str, python_version: str, arch: str
    ):
        """Test that single character layer names are handled correctly.

        **Validates: Requirements 6.1 (Property 3)**
        """
        path = format_release_s3_path(layer_name, version, python_version, arch)

        # Property: Path should still be valid with single char layer name
        assert f"/{layer_name}/" in path, (
            f"Path should contain single char layer name, got: {path}"
        )

    @settings(max_examples=100)
    @given(
        layer_name=layer_name_strategy,
        version=st.from_regex(r"[0-9]+\.[0-9]+", fullmatch=True),  # Various versions
        python_version=python_version_strategy,
        arch=arch_strategy,
    )
    def test_various_version_formats(
        self, layer_name: str, version: str, python_version: str, arch: str
    ):
        """Test that various version formats are handled correctly.

        **Validates: Requirements 6.1 (Property 3)**
        """
        path = format_release_s3_path(layer_name, version, python_version, arch)

        # Property: Path should contain the exact version
        assert f"/{version}/" in path, (
            f"Path should contain version '{version}', got: {path}"
        )

    @settings(max_examples=100)
    @given(pr_number=st.integers(min_value=1, max_value=1))
    def test_minimum_pr_number(self, pr_number: int):
        """Test that minimum PR number (1) is handled correctly.

        **Validates: Requirements 4.3 (Property 3)**
        """
        path = format_test_s3_path(pr_number, "common", "1.0", "312", "x86_64")

        # Property: Path should contain PR number 1
        assert "test/1/" in path, f"Path should contain 'test/1/', got: {path}"

    @settings(max_examples=100)
    @given(pr_number=st.integers(min_value=100000, max_value=999999))
    def test_large_pr_number(self, pr_number: int):
        """Test that large PR numbers are handled correctly.

        **Validates: Requirements 4.3 (Property 3)**
        """
        path = format_test_s3_path(pr_number, "common", "1.0", "312", "x86_64")

        # Property: Path should contain the large PR number
        assert f"test/{pr_number}/" in path, (
            f"Path should contain 'test/{pr_number}/', got: {path}"
        )
