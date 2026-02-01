#!/usr/bin/env python3
"""Unit tests for validate-config.py."""

import sys
from pathlib import Path

import pytest

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from importlib.machinery import SourceFileLoader
from importlib.util import module_from_spec, spec_from_loader

# Load validate-config.py as a module
script_path = Path(__file__).parent.parent / "scripts" / "validate-config.py"
loader = SourceFileLoader("validate_config", str(script_path))
spec = spec_from_loader("validate_config", loader)
validate_config_module = module_from_spec(spec)
loader.exec_module(validate_config_module)

load_config = validate_config_module.load_config
validate_config = validate_config_module.validate_config
get_platform = validate_config_module.get_platform
get_build_matrix = validate_config_module.get_build_matrix
get_version = validate_config_module.get_version
check_version_exists = validate_config_module.check_version_exists


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


class TestCheckVersionExists:
    """Tests for check_version_exists function.

    **Validates: Requirements 3.1, 3.2, 3.3**
    """

    def test_check_version_exists_returns_true_when_artifacts_exist(
        self, tmp_path, monkeypatch
    ):
        """Test that check_version_exists returns True when S3 lists objects."""
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
        # Mock subprocess.run to simulate S3 listing objects
        import subprocess

        class MockResult:
            returncode = 0
            stdout = "2024-01-01 12:00:00  12345 py312-x86_64.zip\n"

        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockResult())

        result = check_version_exists(tmp_path, "test-bucket", "layers")

        assert result is True

    def test_check_version_exists_returns_false_when_no_artifacts(
        self, tmp_path, monkeypatch
    ):
        """Test that check_version_exists returns False when S3 returns empty."""
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
        # Mock subprocess.run to simulate S3 returning empty (no objects)
        import subprocess

        class MockResult:
            returncode = 0
            stdout = ""

        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockResult())

        result = check_version_exists(tmp_path, "test-bucket", "layers")

        assert result is False

    def test_check_version_exists_returns_false_when_s3_fails(
        self, tmp_path, monkeypatch
    ):
        """Test that check_version_exists returns False when S3 command fails."""
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
        # Mock subprocess.run to simulate S3 command failure
        import subprocess

        class MockResult:
            returncode = 1
            stdout = ""

        monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: MockResult())

        result = check_version_exists(tmp_path, "test-bucket", "layers")

        assert result is False

    def test_check_version_exists_uses_correct_s3_path(self, tmp_path, monkeypatch):
        """Test that check_version_exists constructs the correct S3 path."""
        # Create a named subdirectory to control the layer name
        layer_dir = tmp_path / "mytest"
        layer_dir.mkdir()
        layer_pyproject = layer_dir / "pyproject.toml"
        layer_pyproject.write_text("""
[project]
name = "mytest"
version = "2.5"

[tool.lambda_layer]
python_versions = ["3.12"]
architectures = ["x86_64"]
platforms = { x86_64 = "x86_64-manylinux2014" }
""")
        # Mock subprocess.run to capture the S3 path
        import subprocess

        captured_args = []

        class MockResult:
            returncode = 0
            stdout = ""

        def mock_run(*args, **kwargs):
            captured_args.append(args[0])
            return MockResult()

        monkeypatch.setattr(subprocess, "run", mock_run)

        check_version_exists(layer_dir, "my-bucket", "custom-prefix")

        # Verify the S3 path was constructed correctly
        assert len(captured_args) == 1
        assert captured_args[0] == [
            "aws",
            "s3",
            "ls",
            "s3://my-bucket/custom-prefix/mytest/2.5/",
        ]

    def test_check_version_exists_default_prefix(self, tmp_path, monkeypatch):
        """Test that check_version_exists uses 'layers' as default prefix."""
        layer_dir = tmp_path / "common"
        layer_dir.mkdir()
        pyproject = layer_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "common"
version = "1.0"

[tool.lambda_layer]
python_versions = ["3.12"]
architectures = ["x86_64"]
platforms = { x86_64 = "x86_64-manylinux2014" }
""")
        import subprocess

        captured_args = []

        class MockResult:
            returncode = 0
            stdout = ""

        def mock_run(*args, **kwargs):
            captured_args.append(args[0])
            return MockResult()

        monkeypatch.setattr(subprocess, "run", mock_run)

        check_version_exists(layer_dir, "test-bucket")

        # Verify default prefix is "layers"
        assert len(captured_args) == 1
        assert captured_args[0] == [
            "aws",
            "s3",
            "ls",
            "s3://test-bucket/layers/common/1.0/",
        ]
