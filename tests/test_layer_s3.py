#!/usr/bin/env python3
"""Unit tests for layer_s3.py.

This module tests the S3 artifact operations including:
- s3_object_exists: Check if an S3 object exists
- check_artifacts: Check if all expected artifacts exist in S3
- check_version_exists: Check if any artifact exists for a version
- upload_layer: Upload layer artifacts to S3

Uses mocks for boto3 to avoid actual S3 calls.

**Validates: Requirements 5.2, 5.3**
"""

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from botocore.exceptions import ClientError

# Add scripts directory to path
sys.path.insert(0, str(Path(__file__).parent.parent / "scripts"))

from layer_s3 import (
    check_artifacts,
    check_version_exists,
    get_file_size_human,
    s3_object_exists,
    upload_layer,
)


class TestS3ObjectExists:
    """Tests for s3_object_exists function."""

    def test_object_exists_returns_true(self):
        """Test that s3_object_exists returns True when object exists."""
        mock_client = MagicMock()
        mock_client.head_object.return_value = {}

        result = s3_object_exists(mock_client, "test-bucket", "test-key")

        assert result is True
        mock_client.head_object.assert_called_once_with(
            Bucket="test-bucket", Key="test-key"
        )

    def test_object_not_exists_returns_false(self):
        """Test that s3_object_exists returns False when object doesn't exist."""
        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "HeadObject",
        )

        result = s3_object_exists(mock_client, "test-bucket", "test-key")

        assert result is False

    def test_other_error_raises(self):
        """Test that s3_object_exists raises on non-404 errors."""
        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "403", "Message": "Forbidden"}},
            "HeadObject",
        )

        with pytest.raises(ClientError):
            s3_object_exists(mock_client, "test-bucket", "test-key")


class TestCheckVersionExists:
    """Tests for check_version_exists function."""

    def test_version_exists_returns_true(self, monkeypatch):
        """Test that check_version_exists returns True when artifacts exist."""
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {"KeyCount": 1}
        monkeypatch.setattr("layer_s3.boto3.client", lambda service: mock_client)

        result = check_version_exists("common", "1.0", "test-bucket")

        assert result is True
        mock_client.list_objects_v2.assert_called_once_with(
            Bucket="test-bucket",
            Prefix="layers/common/1.0/",
            MaxKeys=1,
        )

    def test_version_not_exists_returns_false(self, monkeypatch):
        """Test that check_version_exists returns False when no artifacts."""
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {"KeyCount": 0}
        monkeypatch.setattr("layer_s3.boto3.client", lambda service: mock_client)

        result = check_version_exists("common", "1.0", "test-bucket")

        assert result is False

    def test_version_exists_custom_prefix(self, monkeypatch):
        """Test that check_version_exists uses custom prefix."""
        mock_client = MagicMock()
        mock_client.list_objects_v2.return_value = {"KeyCount": 1}
        monkeypatch.setattr("layer_s3.boto3.client", lambda service: mock_client)

        result = check_version_exists("common", "1.0", "test-bucket", prefix="test/123")

        assert result is True
        mock_client.list_objects_v2.assert_called_once_with(
            Bucket="test-bucket",
            Prefix="test/123/common/1.0/",
            MaxKeys=1,
        )


class TestCheckArtifacts:
    """Tests for check_artifacts function."""

    def test_all_artifacts_found(self, tmp_path, monkeypatch):
        """Test check_artifacts returns True when all artifacts exist."""
        # Create layer directory with pyproject.toml
        layer_dir = tmp_path / "layers" / "common"
        layer_dir.mkdir(parents=True)
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

        # Mock LAYERS_DIR to use tmp_path
        monkeypatch.setattr("layer_s3.LAYERS_DIR", tmp_path / "layers")

        # Mock boto3 client
        mock_client = MagicMock()
        mock_client.head_object.return_value = {}  # Object exists
        monkeypatch.setattr("layer_s3.boto3.client", lambda service: mock_client)

        result = check_artifacts("common", "1.0", "test-bucket")

        assert result is True

    def test_some_artifacts_missing(self, tmp_path, monkeypatch):
        """Test check_artifacts returns False when some artifacts missing."""
        # Create layer directory with pyproject.toml
        layer_dir = tmp_path / "layers" / "common"
        layer_dir.mkdir(parents=True)
        pyproject = layer_dir / "pyproject.toml"
        pyproject.write_text("""
[project]
name = "common"
version = "1.0"

[tool.lambda_layer]
python_versions = ["3.12"]
architectures = ["x86_64", "arm64"]
platforms = { x86_64 = "x86_64-manylinux2014", arm64 = "aarch64-manylinux2014" }
""")

        # Mock LAYERS_DIR to use tmp_path
        monkeypatch.setattr("layer_s3.LAYERS_DIR", tmp_path / "layers")

        # Mock boto3 client - first artifact exists, second doesn't
        mock_client = MagicMock()
        call_count = [0]

        def head_object_side_effect(Bucket, Key):
            call_count[0] += 1
            if call_count[0] == 1:
                return {}  # First artifact exists
            raise ClientError(
                {"Error": {"Code": "404", "Message": "Not Found"}},
                "HeadObject",
            )

        mock_client.head_object.side_effect = head_object_side_effect
        monkeypatch.setattr("layer_s3.boto3.client", lambda service: mock_client)

        result = check_artifacts("common", "1.0", "test-bucket")

        assert result is False

    def test_layer_directory_not_found(self, tmp_path, monkeypatch):
        """Test check_artifacts returns False when layer directory doesn't exist."""
        # Mock LAYERS_DIR to use tmp_path (no layer directory created)
        monkeypatch.setattr("layer_s3.LAYERS_DIR", tmp_path / "layers")

        result = check_artifacts("nonexistent", "1.0", "test-bucket")

        assert result is False


class TestGetFileSizeHuman:
    """Tests for get_file_size_human function."""

    def test_bytes(self, tmp_path):
        """Test file size in bytes."""
        test_file = tmp_path / "small.txt"
        test_file.write_bytes(b"x" * 500)

        result = get_file_size_human(test_file)

        assert result == "500.0B"

    def test_kilobytes(self, tmp_path):
        """Test file size in kilobytes."""
        test_file = tmp_path / "medium.txt"
        test_file.write_bytes(b"x" * 2048)

        result = get_file_size_human(test_file)

        assert result == "2.0KB"

    def test_megabytes(self, tmp_path):
        """Test file size in megabytes."""
        test_file = tmp_path / "large.txt"
        test_file.write_bytes(b"x" * (2 * 1024 * 1024))

        result = get_file_size_human(test_file)

        assert result == "2.0MB"


class TestUploadLayer:
    """Tests for upload_layer function."""

    def test_upload_success(self, tmp_path, monkeypatch):
        """Test successful upload of layer artifacts."""
        # Create build directory with ZIP file
        build_dir = tmp_path / ".build" / "common" / "dist"
        build_dir.mkdir(parents=True)
        zip_file = build_dir / "py312-x86_64.zip"
        zip_file.write_bytes(b"fake zip content")

        # Mock BUILD_ROOT
        monkeypatch.setattr("layer_s3.BUILD_ROOT", tmp_path / ".build")

        # Mock boto3 client
        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "HeadObject",
        )  # Object doesn't exist
        monkeypatch.setattr("layer_s3.boto3.client", lambda service: mock_client)

        result = upload_layer("common", "1.0", "test-bucket")

        assert result is True
        mock_client.upload_file.assert_called_once()

    def test_upload_dry_run(self, tmp_path, monkeypatch):
        """Test dry-run mode doesn't actually upload."""
        # Create build directory with ZIP file
        build_dir = tmp_path / ".build" / "common" / "dist"
        build_dir.mkdir(parents=True)
        zip_file = build_dir / "py312-x86_64.zip"
        zip_file.write_bytes(b"fake zip content")

        # Mock BUILD_ROOT
        monkeypatch.setattr("layer_s3.BUILD_ROOT", tmp_path / ".build")

        # Mock boto3 client
        mock_client = MagicMock()
        mock_client.head_object.side_effect = ClientError(
            {"Error": {"Code": "404", "Message": "Not Found"}},
            "HeadObject",
        )
        monkeypatch.setattr("layer_s3.boto3.client", lambda service: mock_client)

        result = upload_layer("common", "1.0", "test-bucket", dry_run=True)

        assert result is True
        mock_client.upload_file.assert_not_called()

    def test_upload_immutability_check(self, tmp_path, monkeypatch):
        """Test that upload fails when artifact already exists in release prefix."""
        # Create build directory with ZIP file
        build_dir = tmp_path / ".build" / "common" / "dist"
        build_dir.mkdir(parents=True)
        zip_file = build_dir / "py312-x86_64.zip"
        zip_file.write_bytes(b"fake zip content")

        # Mock BUILD_ROOT
        monkeypatch.setattr("layer_s3.BUILD_ROOT", tmp_path / ".build")

        # Mock boto3 client - object already exists
        mock_client = MagicMock()
        mock_client.head_object.return_value = {}  # Object exists
        monkeypatch.setattr("layer_s3.boto3.client", lambda service: mock_client)

        result = upload_layer("common", "1.0", "test-bucket")

        assert result is False
        mock_client.upload_file.assert_not_called()

    def test_upload_no_build_directory(self, tmp_path, monkeypatch):
        """Test upload fails when build directory doesn't exist."""
        # Mock BUILD_ROOT to non-existent directory
        monkeypatch.setattr("layer_s3.BUILD_ROOT", tmp_path / ".build")

        result = upload_layer("common", "1.0", "test-bucket")

        assert result is False

    def test_upload_test_prefix_allows_overwrite(self, tmp_path, monkeypatch):
        """Test that upload to test prefix allows overwriting."""
        # Create build directory with ZIP file
        build_dir = tmp_path / ".build" / "common" / "dist"
        build_dir.mkdir(parents=True)
        zip_file = build_dir / "py312-x86_64.zip"
        zip_file.write_bytes(b"fake zip content")

        # Mock BUILD_ROOT
        monkeypatch.setattr("layer_s3.BUILD_ROOT", tmp_path / ".build")

        # Mock boto3 client - object already exists
        mock_client = MagicMock()
        mock_client.head_object.return_value = {}  # Object exists
        monkeypatch.setattr("layer_s3.boto3.client", lambda service: mock_client)

        # Use test prefix (not "layers")
        result = upload_layer("common", "1.0", "test-bucket", prefix="test/123")

        assert result is True
        mock_client.upload_file.assert_called_once()
