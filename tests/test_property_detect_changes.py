#!/usr/bin/env python3
"""Property-based tests for detect-changes.sh script.

This module contains property-based tests using hypothesis to verify
the change detection functionality across many generated inputs.

Feature: auto-detect-layer-release, Property 1: Change Detection Path Filtering
"""

from typing import Callable

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

# =============================================================================
# Path Filtering Logic (Pure Python implementation for testing)
# =============================================================================


def extract_layer_names(file_paths: list[str]) -> list[str]:
    """Extract unique layer names from a list of file paths.

    This is a pure Python implementation of the path filtering logic
    used in detect-changes.sh. It filters paths to only those matching
    `layers/<name>/` and returns unique layer names.

    Args:
        file_paths: List of file paths from a git diff.

    Returns:
        Sorted list of unique layer names.
    """
    layer_names = set()

    for path in file_paths:
        # Match paths that start with "layers/" and have at least one more component
        # Pattern: layers/<name>/... where <name> is non-empty
        if path.startswith("layers/"):
            parts = path.split("/")
            if len(parts) >= 2 and parts[1]:  # Must have a layer name
                layer_names.add(parts[1])

    return sorted(layer_names)


# =============================================================================
# Hypothesis Strategies
# =============================================================================

# Strategy for valid layer names (alphanumeric with hyphens, like "common", "my-utils")
layer_name_strategy = st.from_regex(r"[a-z][a-z0-9\-]{0,20}", fullmatch=True)

# Strategy for file extensions commonly found in layers
file_extension_strategy = st.sampled_from(
    [".py", ".toml", ".lock", ".txt", ".md", ".yaml", ".yml", ".json", ""]
)

# Strategy for file names within a layer
layer_file_name_strategy = st.sampled_from(
    [
        "pyproject.toml",
        "uv.lock",
        "README.md",
        "src/helper.py",
        "src/utils/common.py",
        "src/__init__.py",
        "tests/test_layer.py",
    ]
)

# Strategy for non-layer paths (paths outside layers/ directory)
non_layer_path_strategy = st.sampled_from(
    [
        "README.md",
        "terraform/main.tf",
        "terraform/variables.tf",
        "terraform/outputs.tf",
        "scripts/build-layer.sh",
        "scripts/upload-layer.sh",
        ".github/workflows/ci.yml",
        ".gitignore",
        "pyproject.toml",
        "docs/README.md",
        ".kiro/specs/feature/design.md",
    ]
)


@st.composite
def layer_path_strategy(draw: Callable) -> str:
    """Generate a valid layer file path.

    Format: layers/<name>/<file>
    """
    layer_name = draw(layer_name_strategy)
    file_name = draw(layer_file_name_strategy)
    return f"layers/{layer_name}/{file_name}"


@st.composite
def mixed_file_paths_strategy(draw: Callable) -> tuple[list[str], set[str]]:
    """Generate a mixed list of file paths with expected layer names.

    Returns:
        A tuple of (file_paths, expected_layer_names) where:
        - file_paths is a list of mixed layer and non-layer paths
        - expected_layer_names is the set of layer names that should be extracted
    """
    # Generate some layer paths
    num_layer_paths = draw(st.integers(min_value=0, max_value=10))
    layer_paths = []
    expected_layers = set()

    for _ in range(num_layer_paths):
        layer_name = draw(layer_name_strategy)
        file_name = draw(layer_file_name_strategy)
        layer_paths.append(f"layers/{layer_name}/{file_name}")
        expected_layers.add(layer_name)

    # Generate some non-layer paths
    num_non_layer_paths = draw(st.integers(min_value=0, max_value=10))
    non_layer_paths = draw(
        st.lists(
            non_layer_path_strategy, min_size=num_non_layer_paths, max_size=num_non_layer_paths
        )
    )

    # Combine and shuffle
    all_paths = layer_paths + non_layer_paths
    shuffled_paths = draw(st.permutations(all_paths))

    return list(shuffled_paths), expected_layers


# =============================================================================
# Property-Based Tests
# =============================================================================


@pytest.mark.property
class TestChangeDetectionPathFiltering:
    """Property-based tests for change detection path filtering.

    Feature: auto-detect-layer-release, Property 1: Change Detection Path Filtering

    **Validates: Requirements 1.1, 1.2, 1.3**

    Property 1: For any set of file paths from a git diff, the change detection
    script SHALL return only unique layer directory names that match the pattern
    `layers/<name>/`.
    """

    @settings(max_examples=100)
    @given(data=mixed_file_paths_strategy())
    def test_extracts_only_layer_paths(self, data: tuple[list[str], set[str]]):
        """Test that only paths matching layers/<name>/ are extracted.

        **Validates: Requirements 1.1, 1.2, 1.3 (Property 1)**

        This property verifies that:
        1. All returned layer names come from paths starting with "layers/"
        2. Non-layer paths (terraform/, scripts/, etc.) are ignored
        3. The result contains only unique layer names
        """
        file_paths, expected_layers = data

        result = extract_layer_names(file_paths)

        # Property: Result should match expected layers
        assert set(result) == expected_layers, (
            f"Expected layers {expected_layers}, got {set(result)} from paths {file_paths}"
        )

    @settings(max_examples=100)
    @given(file_paths=st.lists(non_layer_path_strategy, min_size=0, max_size=20))
    def test_non_layer_paths_return_empty(self, file_paths: list[str]):
        """Test that non-layer paths always return empty list.

        **Validates: Requirements 1.3 (Property 1)**

        This property verifies that when only non-layer paths are provided
        (terraform/, scripts/, README.md, etc.), the result is always empty.
        """
        result = extract_layer_names(file_paths)

        # Property: Non-layer paths should never produce layer names
        assert result == [], (
            f"Expected empty list for non-layer paths, got {result} from paths {file_paths}"
        )

    @settings(max_examples=100)
    @given(layer_names=st.lists(layer_name_strategy, min_size=1, max_size=10, unique=True))
    def test_unique_layer_names_returned(self, layer_names: list[str]):
        """Test that duplicate layer paths result in unique layer names.

        **Validates: Requirements 1.1, 1.2 (Property 1)**

        This property verifies that even when multiple files from the same
        layer are changed, only unique layer names are returned.
        """
        # Generate multiple paths for each layer (simulating multiple file changes)
        file_paths = []
        for layer_name in layer_names:
            # Add multiple files from the same layer
            file_paths.append(f"layers/{layer_name}/pyproject.toml")
            file_paths.append(f"layers/{layer_name}/uv.lock")
            file_paths.append(f"layers/{layer_name}/src/helper.py")

        result = extract_layer_names(file_paths)

        # Property: Result should have no duplicates
        assert len(result) == len(set(result)), f"Result contains duplicates: {result}"

        # Property: Result should contain exactly the input layer names
        assert set(result) == set(layer_names), (
            f"Expected layers {set(layer_names)}, got {set(result)}"
        )

    @settings(max_examples=100)
    @given(file_paths=st.lists(layer_path_strategy(), min_size=0, max_size=20))
    def test_result_is_sorted(self, file_paths: list[str]):
        """Test that the result is always sorted alphabetically.

        **Validates: Requirements 1.1, 1.2 (Property 1)**

        This property verifies that the returned layer names are sorted,
        which matches the behavior of the shell script using `sort -u`.
        """
        result = extract_layer_names(file_paths)

        # Property: Result should be sorted
        assert result == sorted(result), f"Result is not sorted: {result}"

    @settings(max_examples=100)
    @given(
        layer_paths=st.lists(layer_path_strategy(), min_size=0, max_size=10),
        non_layer_paths=st.lists(non_layer_path_strategy, min_size=0, max_size=10),
    )
    def test_mixed_paths_filters_correctly(
        self, layer_paths: list[str], non_layer_paths: list[str]
    ):
        """Test that mixed layer and non-layer paths are filtered correctly.

        **Validates: Requirements 1.1, 1.2, 1.3 (Property 1)**

        This property verifies the example from the design document:
        - Input: ["layers/common/pyproject.toml", "layers/common/uv.lock",
                  "README.md", "terraform/main.tf", "layers/utils/src/helper.py"]
        - Output: ["common", "utils"]
        """
        all_paths = layer_paths + non_layer_paths

        result = extract_layer_names(all_paths)

        # Extract expected layer names from layer_paths only
        expected_layers = set()
        for path in layer_paths:
            if path.startswith("layers/"):
                parts = path.split("/")
                if len(parts) >= 2 and parts[1]:
                    expected_layers.add(parts[1])

        # Property: Result should match expected layers from layer_paths only
        assert set(result) == expected_layers, (
            f"Expected {expected_layers}, got {set(result)} "
            f"from layer_paths={layer_paths}, non_layer_paths={non_layer_paths}"
        )

    @settings(max_examples=100)
    @given(st.data())
    def test_empty_input_returns_empty(self, data):
        """Test that empty input always returns empty list.

        **Validates: Requirements 1.3 (Property 1)**
        """
        result = extract_layer_names([])

        # Property: Empty input should return empty output
        assert result == [], f"Expected empty list, got {result}"

    @settings(max_examples=100)
    @given(layer_name=layer_name_strategy)
    def test_single_layer_single_file(self, layer_name: str):
        """Test that a single layer file returns that layer name.

        **Validates: Requirements 1.1 (Property 1)**
        """
        file_paths = [f"layers/{layer_name}/pyproject.toml"]

        result = extract_layer_names(file_paths)

        # Property: Single layer file should return single layer name
        assert result == [layer_name], f"Expected [{layer_name}], got {result}"


@pytest.mark.property
class TestEdgeCases:
    """Edge case tests for path filtering.

    Feature: auto-detect-layer-release, Property 1: Change Detection Path Filtering

    **Validates: Requirements 1.3**
    """

    @settings(max_examples=100)
    @given(layer_name=layer_name_strategy)
    def test_layers_prefix_only_not_matched(self, layer_name: str):
        """Test that 'layers' without trailing content is not matched.

        **Validates: Requirements 1.3 (Property 1)**

        Paths like "layers" or "layers/" without a layer name should not
        produce any results.
        """
        # These paths should NOT match
        invalid_paths = [
            "layers",
            "layers/",
        ]

        result = extract_layer_names(invalid_paths)

        # Property: Invalid layer paths should return empty
        assert result == [], f"Expected empty list for invalid paths, got {result}"

    @settings(max_examples=100)
    @given(layer_name=layer_name_strategy)
    def test_layerslike_paths_not_matched(self, layer_name: str):
        """Test that paths starting with 'layers' but not 'layers/' are ignored.

        **Validates: Requirements 1.3 (Property 1)**

        Paths like "layers_backup/common/file.py" should not match.
        """
        # These paths should NOT match (they don't start with "layers/")
        invalid_paths = [
            f"layers_backup/{layer_name}/pyproject.toml",
            f"layersold/{layer_name}/uv.lock",
            f"my-layers/{layer_name}/src/helper.py",
        ]

        result = extract_layer_names(invalid_paths)

        # Property: Paths not starting with "layers/" should return empty
        assert result == [], f"Expected empty list for non-layers paths, got {result}"

    @settings(max_examples=100)
    @given(
        layer_name=layer_name_strategy,
        deep_path=st.lists(
            st.from_regex(r"[a-z][a-z0-9]{0,10}", fullmatch=True), min_size=1, max_size=5
        ),
    )
    def test_deeply_nested_paths_extract_layer_name(self, layer_name: str, deep_path: list[str]):
        """Test that deeply nested paths still extract the correct layer name.

        **Validates: Requirements 1.1 (Property 1)**

        Paths like "layers/common/src/utils/helpers/deep/file.py" should
        still extract "common" as the layer name.
        """
        nested_path = "/".join(deep_path)
        file_path = f"layers/{layer_name}/{nested_path}/file.py"

        result = extract_layer_names([file_path])

        # Property: Layer name should be extracted regardless of nesting depth
        assert result == [layer_name], (
            f"Expected [{layer_name}], got {result} from path {file_path}"
        )
