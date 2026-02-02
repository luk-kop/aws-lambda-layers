#!/usr/bin/env python3
"""Unit tests for layer_config.py.

This module tests the layer configuration utilities including:
- Configuration loading and validation from pyproject.toml
- Platform and build matrix extraction
- CI matrix building from file paths

Migrated from test_validate_config.py and test_build_matrix.py.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from layer_config import (
    build_output,
    extract_layer_names,
    get_build_config,
    get_build_matrix,
    get_platform,
    get_version,
    load_config,
    validate_config,
)

SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "layer_config.py"


# =============================================================================
# Tests migrated from test_validate_config.py
# =============================================================================


class TestLoadConfig:
    """Tests for load_config function."""

    def test_load_valid_config(self, tmp_path):
        """Test loading a valid pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "1.0"

[tool.lambda_layer]
python_versions = ["3.12"]
architectures = ["x86_64"]
platforms = { x86_64 = "x86_64-manylinux2014" }
""")
        config = load_config(tmp_path)
        assert config["project"]["name"] == "test"
        assert config["project"]["version"] == "1.0"

    def test_load_missing_file(self, tmp_path):
        """Test loading from directory without pyproject.toml."""
        with pytest.raises(FileNotFoundError):
            load_config(tmp_path)


class TestValidateConfig:
    """Tests for validate_config function."""

    def test_valid_config(self):
        """Test validation of a valid configuration."""
        config = {
            "project": {"name": "test", "version": "1.0", "requires-python": ">=3.11"},
            "tool": {
                "lambda_layer": {
                    "python_versions": ["3.11", "3.12"],
                    "architectures": ["x86_64"],
                    "platforms": {"x86_64": "x86_64-manylinux2014"},
                }
            },
        }
        errors = validate_config(config, "test")
        assert errors == []

    def test_missing_project_section(self):
        """Test validation fails when [project] section is missing."""
        config = {
            "tool": {
                "lambda_layer": {
                    "python_versions": ["3.12"],
                    "architectures": ["x86_64"],
                    "platforms": {"x86_64": "manylinux2014_x86_64"},
                }
            }
        }
        errors = validate_config(config, "test")
        assert len(errors) == 1
        assert "Missing [project] section" in errors[0]

    def test_missing_lambda_layer_section(self):
        """Test validation fails when [tool.lambda_layer] section is missing."""
        config = {"project": {"name": "test", "version": "1.0"}}
        errors = validate_config(config, "test")
        assert len(errors) == 1
        assert "Missing [tool.lambda_layer] section" in errors[0]

    def test_missing_required_fields(self):
        """Test validation fails when required fields are missing."""
        config = {
            "project": {"name": "test", "version": "1.0"},
            "tool": {
                "lambda_layer": {
                    "python_versions": ["3.12"]
                    # Missing architectures and platforms
                }
            },
        }
        errors = validate_config(config, "test")
        assert len(errors) == 2
        assert any("architectures" in e for e in errors)
        assert any("platforms" in e for e in errors)

    def test_python_version_not_allowed(self):
        """Test validation fails when python_versions violates requires-python."""
        config = {
            "project": {"name": "test", "version": "1.0", "requires-python": ">=3.12"},
            "tool": {
                "lambda_layer": {
                    "python_versions": ["3.10", "3.12"],  # 3.10 not allowed
                    "architectures": ["x86_64"],
                    "platforms": {"x86_64": "x86_64-manylinux2014"},
                }
            },
        }
        errors = validate_config(config, "test")
        assert len(errors) == 1
        assert "Python 3.10 not allowed" in errors[0]

    def test_missing_platform_mapping(self):
        """Test validation fails when platform mapping is missing for architecture."""
        config = {
            "project": {"name": "test", "version": "1.0", "requires-python": ">=3.11"},
            "tool": {
                "lambda_layer": {
                    "python_versions": ["3.12"],
                    "architectures": ["x86_64", "arm64"],
                    "platforms": {"x86_64": "x86_64-manylinux2014"},  # Missing arm64
                }
            },
        }
        errors = validate_config(config, "test")
        assert len(errors) == 1
        assert "Missing platform mapping for architecture 'arm64'" in errors[0]

    def test_name_mismatch(self):
        """Test validation fails when project name doesn't match directory name."""
        config = {
            "project": {
                "name": "wrong-name",
                "version": "1.0",
                "requires-python": ">=3.11",
            },
            "tool": {
                "lambda_layer": {
                    "python_versions": ["3.12"],
                    "architectures": ["x86_64"],
                    "platforms": {"x86_64": "x86_64-manylinux2014"},
                }
            },
        }
        errors = validate_config(config, "correct-name")
        assert len(errors) == 1
        assert "does not match directory name" in errors[0]

    def test_missing_name(self):
        """Test validation fails when project name is missing."""
        config = {
            "project": {"version": "1.0", "requires-python": ">=3.11"},
            "tool": {
                "lambda_layer": {
                    "python_versions": ["3.12"],
                    "architectures": ["x86_64"],
                    "platforms": {"x86_64": "x86_64-manylinux2014"},
                }
            },
        }
        errors = validate_config(config, "test")
        assert len(errors) == 1
        assert "Missing 'name' field" in errors[0]


class TestGetPlatform:
    """Tests for get_platform function."""

    def test_get_platform_x86_64(self, tmp_path):
        """Test getting platform for x86_64 architecture."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "1.0"

[tool.lambda_layer]
python_versions = ["3.12"]
architectures = ["x86_64", "arm64"]
platforms = { x86_64 = "x86_64-manylinux2014", arm64 = "aarch64-manylinux2014" }
""")
        assert get_platform(tmp_path, "x86_64") == "x86_64-manylinux2014"

    def test_get_platform_arm64(self, tmp_path):
        """Test getting platform for arm64 architecture."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "1.0"

[tool.lambda_layer]
python_versions = ["3.12"]
architectures = ["x86_64", "arm64"]
platforms = { x86_64 = "x86_64-manylinux2014", arm64 = "aarch64-manylinux2014" }
""")
        assert get_platform(tmp_path, "arm64") == "aarch64-manylinux2014"


class TestGetBuildMatrix:
    """Tests for get_build_matrix function."""

    def test_single_variant(self, tmp_path):
        """Test build matrix with single Python version and architecture."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "1.0"

[tool.lambda_layer]
python_versions = ["3.12"]
architectures = ["x86_64"]
platforms = { x86_64 = "x86_64-manylinux2014" }
""")
        matrix = get_build_matrix(tmp_path)
        assert len(matrix) == 1
        assert matrix[0] == {
            "python": "3.12",
            "arch": "x86_64",
            "platform": "x86_64-manylinux2014",
        }

    def test_multiple_variants(self, tmp_path):
        """Test build matrix with multiple Python versions and architectures."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "1.0"

[tool.lambda_layer]
python_versions = ["3.11", "3.12"]
architectures = ["x86_64", "arm64"]
platforms = { x86_64 = "x86_64-manylinux2014", arm64 = "aarch64-manylinux2014" }
""")
        matrix = get_build_matrix(tmp_path)
        assert len(matrix) == 4

        # Verify all combinations exist
        expected = [
            {"python": "3.11", "arch": "x86_64", "platform": "x86_64-manylinux2014"},
            {"python": "3.11", "arch": "arm64", "platform": "aarch64-manylinux2014"},
            {"python": "3.12", "arch": "x86_64", "platform": "x86_64-manylinux2014"},
            {"python": "3.12", "arch": "arm64", "platform": "aarch64-manylinux2014"},
        ]
        for item in expected:
            assert item in matrix


class TestGetVersion:
    """Tests for get_version function."""

    def test_get_version(self, tmp_path):
        """Test getting version from pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "2.5"

[tool.lambda_layer]
python_versions = ["3.12"]
architectures = ["x86_64"]
platforms = { x86_64 = "x86_64-manylinux2014" }
""")
        assert get_version(tmp_path) == "2.5"


# =============================================================================
# Tests migrated from test_build_matrix.py
# =============================================================================


def run_layer_config_stdin(
    paths: list[str], cwd: Path | None = None
) -> tuple[int, dict | None, str]:
    """Run layer_config.py with given paths as stdin.

    Args:
        paths: List of file paths to pass via stdin
        cwd: Working directory (defaults to project root)

    Returns:
        Tuple of (exit_code, parsed_json_output, stderr)
    """
    if cwd is None:
        cwd = SCRIPT_PATH.parent.parent

    input_text = "\n".join(paths)
    result = subprocess.run(
        ["python", str(SCRIPT_PATH)],
        input=input_text,
        capture_output=True,
        text=True,
        cwd=cwd,
    )

    parsed_output = None
    if result.returncode == 0 and result.stdout.strip():
        try:
            parsed_output = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            pass

    return result.returncode, parsed_output, result.stderr


class TestExtractLayerNames:
    """Tests for extract_layer_names function."""

    def test_extract_single_layer(self):
        """Test extracting a single layer name."""
        paths = ["layers/common/pyproject.toml"]
        layers = extract_layer_names(paths)
        assert layers == ["common"]

    def test_extract_multiple_layers(self):
        """Test extracting multiple layer names."""
        paths = [
            "layers/common/pyproject.toml",
            "layers/utils/pyproject.toml",
        ]
        layers = extract_layer_names(paths)
        assert layers == ["common", "utils"]

    def test_extract_deduplicates(self):
        """Test that duplicate layer names are deduplicated."""
        paths = [
            "layers/common/pyproject.toml",
            "layers/common/uv.lock",
            "layers/common/src/utils.py",
        ]
        layers = extract_layer_names(paths)
        assert layers == ["common"]

    def test_extract_ignores_non_layer_paths(self):
        """Test that non-layer paths are ignored."""
        paths = [
            "README.md",
            "terraform/main.tf",
            "scripts/build.sh",
        ]
        layers = extract_layer_names(paths)
        assert layers == []

    def test_extract_sorts_alphabetically(self):
        """Test that layer names are sorted alphabetically."""
        paths = [
            "layers/zebra/pyproject.toml",
            "layers/alpha/pyproject.toml",
            "layers/beta/pyproject.toml",
        ]
        layers = extract_layer_names(paths)
        assert layers == ["alpha", "beta", "zebra"]


class TestGetBuildConfig:
    """Tests for get_build_config function."""

    def test_get_build_config(self, tmp_path):
        """Test getting build config from pyproject.toml."""
        pyproject = tmp_path / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "test"
version = "1.0"

[tool.lambda_layer]
python_versions = ["3.11", "3.12"]
architectures = ["x86_64", "arm64"]
platforms = { x86_64 = "x86_64-manylinux2014", arm64 = "aarch64-manylinux2014" }
""")
        config = get_build_config(tmp_path)
        assert config["python_versions"] == ["3.11", "3.12"]
        assert config["architectures"] == ["x86_64", "arm64"]


class TestBuildOutput:
    """Tests for build_output function."""

    def test_build_output_empty(self):
        """Test build_output with empty layer list."""
        output = build_output([])
        assert output["layers"] == []
        assert output["matrix"] == []
        assert output["build_matrix"] == []
        assert output["has_changes"] is False

    def test_build_output_single_layer(self):
        """Test build_output with single layer (uses real 'common' layer)."""
        output = build_output(["common"])
        assert output["layers"] == ["common"]
        assert output["has_changes"] is True
        assert len(output["matrix"]) == 1
        assert output["matrix"][0]["name"] == "common"
        assert "version" in output["matrix"][0]

    def test_build_output_skips_deleted_layer(self, tmp_path, monkeypatch):
        """Test that deleted layers (no directory) are skipped silently."""
        # Point LAYERS_DIR to tmp_path (no layers exist)
        monkeypatch.setattr("layer_config.LAYERS_DIR", tmp_path)

        output = build_output(["nonexistent"])

        assert output["layers"] == []
        assert output["has_changes"] is False

    def test_build_output_errors_on_missing_pyproject(self, tmp_path, monkeypatch):
        """Test that existing dir without pyproject.toml raises error."""
        # Create layer directory without pyproject.toml
        layer_dir = tmp_path / "broken"
        layer_dir.mkdir()

        monkeypatch.setattr("layer_config.LAYERS_DIR", tmp_path)

        with pytest.raises(FileNotFoundError, match="missing pyproject.toml"):
            build_output(["broken"])

    def test_build_output_errors_on_missing_lockfile(self, tmp_path, monkeypatch):
        """Test that existing dir without uv.lock raises error."""
        # Create layer directory with pyproject.toml but no uv.lock
        layer_dir = tmp_path / "nolockfile"
        layer_dir.mkdir()
        (layer_dir / "pyproject.toml").write_text("""
[project]
name = "nolockfile"
version = "1.0"
requires-python = ">=3.11"

[tool.lambda_layer]
python_versions = ["3.12"]
architectures = ["x86_64"]
platforms = { x86_64 = "x86_64-manylinux2014" }
""")

        monkeypatch.setattr("layer_config.LAYERS_DIR", tmp_path)

        with pytest.raises(FileNotFoundError, match="missing uv.lock"):
            build_output(["nolockfile"])


class TestStdinModeEmpty:
    """Tests for empty stdin input."""

    def test_empty_input_returns_no_changes(self):
        """Empty input should return has_changes=false."""
        exit_code, output, stderr = run_layer_config_stdin([])

        assert exit_code == 0
        assert output is not None
        assert output["layers"] == []
        assert output["matrix"] == []
        assert output["build_matrix"] == []
        assert output["has_changes"] is False

    def test_non_layer_paths_return_no_changes(self):
        """Paths not starting with layers/ should be ignored."""
        paths = [
            "README.md",
            "terraform/main.tf",
            "scripts/build.sh",
            ".github/workflows/ci.yml",
        ]
        exit_code, output, stderr = run_layer_config_stdin(paths)

        assert exit_code == 0
        assert output is not None
        assert output["layers"] == []
        assert output["has_changes"] is False


class TestStdinModeSingleLayer:
    """Tests for single layer detection via stdin."""

    def test_single_layer_file(self):
        """Single layer file should be detected."""
        paths = ["layers/common/pyproject.toml"]
        exit_code, output, stderr = run_layer_config_stdin(paths)

        assert exit_code == 0
        assert output is not None
        assert output["layers"] == ["common"]
        assert output["has_changes"] is True
        assert len(output["matrix"]) == 1
        assert output["matrix"][0]["name"] == "common"

    def test_multiple_files_same_layer(self):
        """Multiple files in same layer should result in single layer entry."""
        paths = [
            "layers/common/pyproject.toml",
            "layers/common/uv.lock",
            "layers/common/src/utils.py",
        ]
        exit_code, output, stderr = run_layer_config_stdin(paths)

        assert exit_code == 0
        assert output is not None
        assert output["layers"] == ["common"]
        assert len(output["matrix"]) == 1


class TestStdinModeMixedPaths:
    """Tests for mixed layer and non-layer paths via stdin."""

    def test_mixed_paths_filters_correctly(self):
        """Only layer paths should be included, non-layer paths ignored."""
        paths = [
            "layers/common/pyproject.toml",
            "README.md",
            "terraform/main.tf",
        ]
        exit_code, output, stderr = run_layer_config_stdin(paths)

        assert exit_code == 0
        assert output is not None
        assert output["layers"] == ["common"]


class TestStdinModeOutput:
    """Tests for stdin mode output structure."""

    def test_output_has_required_fields(self):
        """Output should have all required fields."""
        paths = ["layers/common/pyproject.toml"]
        exit_code, output, stderr = run_layer_config_stdin(paths)

        assert exit_code == 0
        assert output is not None
        assert "layers" in output
        assert "matrix" in output
        assert "build_matrix" in output
        assert "has_changes" in output

    def test_matrix_has_name_and_version(self):
        """Matrix entries should have name and version."""
        paths = ["layers/common/pyproject.toml"]
        exit_code, output, stderr = run_layer_config_stdin(paths)

        assert exit_code == 0
        assert output is not None
        assert len(output["matrix"]) == 1
        assert "name" in output["matrix"][0]
        assert "version" in output["matrix"][0]

    def test_build_matrix_is_array(self):
        """Build matrix should be an array."""
        paths = ["layers/common/pyproject.toml"]
        exit_code, output, stderr = run_layer_config_stdin(paths)

        assert exit_code == 0
        assert output is not None
        assert isinstance(output["build_matrix"], list)

    def test_build_matrix_entries_have_required_fields(self):
        """Build matrix entries should have layer, version, python, arch."""
        paths = ["layers/common/pyproject.toml"]
        exit_code, output, stderr = run_layer_config_stdin(paths)

        assert exit_code == 0
        assert output is not None
        assert len(output["build_matrix"]) >= 1

        entry = output["build_matrix"][0]
        assert "layer" in entry
        assert "version" in entry
        assert "python" in entry
        assert "arch" in entry
