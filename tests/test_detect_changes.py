#!/usr/bin/env python3
"""Unit tests for detect-changes.sh script.

This module tests the change detection functionality that identifies which
Lambda layers have been modified between commits or branches.

**Validates: Requirements 11.1**
"""

import json
import subprocess
from pathlib import Path
from typing import Generator

import pytest

# Path to the detect-changes.sh script
SCRIPT_PATH = Path(__file__).parent.parent / "scripts" / "detect-changes.sh"


class GitRepo:
    """Helper class for managing a mock git repository for testing.

    This class provides methods to create and manipulate a temporary git
    repository with layer directories, simulating the project structure
    for testing the detect-changes.sh script.
    """

    def __init__(self, path: Path):
        """Initialize a GitRepo instance.

        Args:
            path: Path to the temporary directory for the git repository.
        """
        self.path = path
        self.layers_dir = path / "layers"

    def init(self) -> None:
        """Initialize a new git repository with an initial commit."""
        subprocess.run(["git", "init"], cwd=self.path, capture_output=True, check=True)
        # Configure git user for commits
        subprocess.run(
            ["git", "config", "user.email", "test@example.com"],
            cwd=self.path,
            capture_output=True,
            check=True,
        )
        subprocess.run(
            ["git", "config", "user.name", "Test User"],
            cwd=self.path,
            capture_output=True,
            check=True,
        )
        # Disable GPG signing for test commits
        subprocess.run(
            ["git", "config", "commit.gpgsign", "false"],
            cwd=self.path,
            capture_output=True,
            check=True,
        )
        # Create initial commit with a README
        readme = self.path / "README.md"
        readme.write_text("# Test Repository\n")
        subprocess.run(
            ["git", "add", "README.md"], cwd=self.path, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", "Initial commit"],
            cwd=self.path,
            capture_output=True,
            check=True,
        )

    def create_layer(
        self,
        name: str,
        version: str = "1.0",
        python_versions: list[str] | None = None,
        architectures: list[str] | None = None,
        commit: bool = True,
    ) -> Path:
        """Create a layer directory with pyproject.toml.

        Args:
            name: Name of the layer (e.g., "common", "utils").
            version: Version string for the layer (default: "1.0").
            python_versions: List of Python versions (default: ["3.12"]).
            architectures: List of architectures (default: ["x86_64"]).
            commit: Whether to commit the changes (default: True).

        Returns:
            Path to the created layer directory.
        """
        if python_versions is None:
            python_versions = ["3.12"]
        if architectures is None:
            architectures = ["x86_64"]

        layer_dir = self.layers_dir / name
        layer_dir.mkdir(parents=True, exist_ok=True)

        # Create pyproject.toml with lambda_layer configuration
        pyproject_content = f'''[project]
name = "{name}"
version = "{version}"
requires-python = ">=3.11"
dependencies = []

[tool.lambda_layer]
python_versions = {json.dumps(python_versions)}
architectures = {json.dumps(architectures)}
platforms = {{ {", ".join(f'{arch} = "manylinux2014_{arch}"' for arch in architectures)} }}
'''
        pyproject = layer_dir / "pyproject.toml"
        pyproject.write_text(pyproject_content)

        # Create empty uv.lock file
        uv_lock = layer_dir / "uv.lock"
        uv_lock.write_text("version = 1\n")

        if commit:
            self.commit_all(f"Add layer {name}")

        return layer_dir

    def modify_layer(self, name: str, commit: bool = True) -> None:
        """Modify an existing layer to simulate a change.

        Args:
            name: Name of the layer to modify.
            commit: Whether to commit the changes (default: True).
        """
        layer_dir = self.layers_dir / name
        if not layer_dir.exists():
            raise ValueError(f"Layer {name} does not exist")

        # Modify the uv.lock file to simulate a dependency change
        uv_lock = layer_dir / "uv.lock"
        current_content = uv_lock.read_text()
        uv_lock.write_text(current_content + "\n# Modified\n")

        if commit:
            self.commit_all(f"Modify layer {name}")

    def update_layer_version(
        self, name: str, new_version: str, commit: bool = True
    ) -> None:
        """Update the version of an existing layer.

        Args:
            name: Name of the layer to update.
            new_version: New version string.
            commit: Whether to commit the changes (default: True).
        """
        layer_dir = self.layers_dir / name
        if not layer_dir.exists():
            raise ValueError(f"Layer {name} does not exist")

        pyproject = layer_dir / "pyproject.toml"
        content = pyproject.read_text()
        # Simple version replacement
        import re

        content = re.sub(r'version = "[^"]+"', f'version = "{new_version}"', content)
        pyproject.write_text(content)

        if commit:
            self.commit_all(f"Update layer {name} to version {new_version}")

    def create_non_layer_file(
        self, path: str, content: str = "", commit: bool = True
    ) -> Path:
        """Create a file outside the layers directory.

        Args:
            path: Relative path from repository root.
            content: File content (default: empty string).
            commit: Whether to commit the changes (default: True).

        Returns:
            Path to the created file.
        """
        file_path = self.path / path
        file_path.parent.mkdir(parents=True, exist_ok=True)
        file_path.write_text(content)

        if commit:
            self.commit_all(f"Add {path}")

        return file_path

    def commit_all(self, message: str) -> None:
        """Stage all changes and create a commit.

        Args:
            message: Commit message.
        """
        subprocess.run(
            ["git", "add", "-A"], cwd=self.path, capture_output=True, check=True
        )
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=self.path,
            capture_output=True,
            check=True,
        )

    def create_branch(self, name: str) -> None:
        """Create and checkout a new branch.

        Args:
            name: Branch name.
        """
        subprocess.run(
            ["git", "checkout", "-b", name],
            cwd=self.path,
            capture_output=True,
            check=True,
        )

    def checkout_branch(self, name: str) -> None:
        """Checkout an existing branch.

        Args:
            name: Branch name.
        """
        subprocess.run(
            ["git", "checkout", name], cwd=self.path, capture_output=True, check=True
        )

    def get_current_commit(self) -> str:
        """Get the current commit SHA.

        Returns:
            The current commit SHA.
        """
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=self.path,
            capture_output=True,
            text=True,
            check=True,
        )
        return result.stdout.strip()


@pytest.fixture
def git_repo(tmp_path: Path) -> Generator[GitRepo, None, None]:
    """Pytest fixture that creates a temporary git repository.

    This fixture creates a new temporary directory with an initialized
    git repository for testing the detect-changes.sh script.

    Yields:
        A GitRepo instance for the temporary repository.
    """
    repo = GitRepo(tmp_path)
    repo.init()
    yield repo


@pytest.fixture
def script_path() -> Path:
    """Pytest fixture that returns the path to detect-changes.sh.

    Returns:
        Path to the detect-changes.sh script.
    """
    return SCRIPT_PATH


def run_detect_changes(
    repo_path: Path, mode: str, base_ref: str | None = None
) -> tuple[int, dict | None, str]:
    """Run the detect-changes.sh script and parse its output.

    Args:
        repo_path: Path to the git repository.
        mode: Detection mode ("pr" or "push").
        base_ref: Base reference for PR mode (required for "pr" mode).

    Returns:
        A tuple of (exit_code, parsed_json_output, stderr).
        If the script fails to produce valid JSON, parsed_json_output will be None.
    """
    cmd = [str(SCRIPT_PATH), mode]
    if base_ref:
        cmd.append(base_ref)

    result = subprocess.run(cmd, cwd=repo_path, capture_output=True, text=True)

    parsed_output = None
    if result.returncode == 0 and result.stdout.strip():
        try:
            parsed_output = json.loads(result.stdout.strip())
        except json.JSONDecodeError:
            pass

    return result.returncode, parsed_output, result.stderr


class TestDetectChangesFixtures:
    """Tests to verify the test fixtures work correctly."""

    def test_git_repo_fixture_creates_valid_repo(self, git_repo: GitRepo):
        """Test that the git_repo fixture creates a valid git repository."""
        assert git_repo.path.exists()
        assert (git_repo.path / ".git").is_dir()

        # Verify we can run git commands
        result = subprocess.run(
            ["git", "status"], cwd=git_repo.path, capture_output=True, text=True
        )
        assert result.returncode == 0

    def test_create_layer_creates_valid_structure(self, git_repo: GitRepo):
        """Test that create_layer creates the expected directory structure."""
        layer_path = git_repo.create_layer("test-layer", version="2.0")

        assert layer_path.exists()
        assert (layer_path / "pyproject.toml").exists()
        assert (layer_path / "uv.lock").exists()

        # Verify pyproject.toml content
        pyproject_content = (layer_path / "pyproject.toml").read_text()
        assert 'name = "test-layer"' in pyproject_content
        assert 'version = "2.0"' in pyproject_content

    def test_modify_layer_creates_change(self, git_repo: GitRepo):
        """Test that modify_layer creates a detectable change."""
        git_repo.create_layer("common")
        initial_commit = git_repo.get_current_commit()

        git_repo.modify_layer("common")
        modified_commit = git_repo.get_current_commit()

        assert initial_commit != modified_commit

    def test_create_non_layer_file(self, git_repo: GitRepo):
        """Test that create_non_layer_file creates files outside layers/."""
        file_path = git_repo.create_non_layer_file("terraform/main.tf", "# Terraform")

        assert file_path.exists()
        assert file_path.read_text() == "# Terraform"


class TestDetectChangesEmpty:
    """Tests for detecting no layer changes.

    **Validates: Requirements 1.4**

    These tests verify that when no layers have changed, the script
    returns an empty list and has_changes is false.
    """

    def test_detect_changes_empty(self, git_repo: GitRepo):
        """Test that no layer changes returns empty list.

        **Validates: Requirements 1.4**

        This test verifies that when no layers have changed between commits,
        the detect-changes.sh script returns an empty result with has_changes=false.

        Steps:
        1. Create a layer in the git repo (establishes baseline)
        2. Make a non-layer change (e.g., modify README)
        3. Run detect-changes.sh in push mode
        4. Verify the output has empty layers array and has_changes is false
        """
        # Step 1: Create a layer to establish baseline
        git_repo.create_layer("common", version="1.0")

        # Step 2: Make a non-layer change (modify README)
        readme_path = git_repo.path / "README.md"
        readme_path.write_text("# Updated Test Repository\n\nSome changes.\n")
        git_repo.commit_all("Update README with non-layer changes")

        # Step 3: Run detect-changes.sh in push mode
        exit_code, output, stderr = run_detect_changes(git_repo.path, "push")

        # Step 4: Verify the output
        assert exit_code == 0, (
            f"Script failed with exit code {exit_code}, stderr: {stderr}"
        )
        assert output is not None, (
            f"Script did not produce valid JSON output, stderr: {stderr}"
        )

        # Verify empty layers array
        assert output["layers"] == [], (
            f"Expected empty layers array, got: {output['layers']}"
        )

        # Verify empty matrix array
        assert output["matrix"] == [], (
            f"Expected empty matrix array, got: {output['matrix']}"
        )

        # Verify empty build_matrix
        assert output["build_matrix"] == {"include": []}, (
            f"Expected empty build_matrix, got: {output['build_matrix']}"
        )

        # Verify has_changes is false
        assert output["has_changes"] is False, (
            f"Expected has_changes to be false, got: {output['has_changes']}"
        )


class TestDetectChangesSingle:
    """Tests for detecting a single layer change.

    **Validates: Requirements 1.1, 1.2**

    These tests verify that when a single layer is modified, it is
    correctly detected and reported with its version.
    """

    def test_detect_changes_single(self, git_repo: GitRepo):
        """Test that single layer change is detected correctly.

        **Validates: Requirements 1.1, 1.2**

        This test verifies that when a single layer is modified between commits,
        the detect-changes.sh script correctly identifies the changed layer and
        returns its name, version, and build matrix.

        Steps:
        1. Create a layer in the git repo (establishes baseline)
        2. Modify the layer (e.g., update uv.lock)
        3. Run detect-changes.sh in push mode
        4. Verify the output contains the layer name, version, and has_changes is true
        """
        # Step 1: Create a layer to establish baseline
        git_repo.create_layer("common", version="1.0")

        # Step 2: Modify the layer to create a detectable change
        git_repo.modify_layer("common")

        # Step 3: Run detect-changes.sh in push mode
        exit_code, output, stderr = run_detect_changes(git_repo.path, "push")

        # Step 4: Verify the output
        assert exit_code == 0, (
            f"Script failed with exit code {exit_code}, stderr: {stderr}"
        )
        assert output is not None, (
            f"Script did not produce valid JSON output, stderr: {stderr}"
        )

        # Verify layers array contains the changed layer
        assert output["layers"] == ["common"], (
            f"Expected layers ['common'], got: {output['layers']}"
        )

        # Verify matrix contains the layer with correct version
        assert output["matrix"] == [{"name": "common", "version": "1.0"}], (
            f"Expected matrix with common v1.0, got: {output['matrix']}"
        )

        # Verify build_matrix contains the expected build variant
        expected_build_matrix = {
            "include": [
                {
                    "layer": "common",
                    "version": "1.0",
                    "python": "3.12",
                    "arch": "x86_64",
                }
            ]
        }
        assert output["build_matrix"] == expected_build_matrix, (
            f"Expected build_matrix {expected_build_matrix}, got: {output['build_matrix']}"
        )

        # Verify has_changes is true
        assert output["has_changes"] is True, (
            f"Expected has_changes to be true, got: {output['has_changes']}"
        )


class TestDetectChangesMultiple:
    """Tests for detecting multiple layer changes.

    **Validates: Requirements 1.1, 1.2**

    These tests verify that when multiple layers are modified, all
    of them are correctly detected and reported.
    """

    def test_detect_changes_multiple(self, git_repo: GitRepo):
        """Test that multiple layer changes are detected correctly.

        **Validates: Requirements 1.1, 1.2**

        This test verifies that when multiple layers are modified between commits,
        the detect-changes.sh script correctly identifies all changed layers and
        returns their names, versions, and build matrices.

        Steps:
        1. Create two layers in the git repo (establishes baseline)
        2. Modify both layers in a single commit
        3. Run detect-changes.sh in push mode
        4. Verify the output contains both layer names and has_changes is true
        """
        # Step 1: Create two layers to establish baseline
        git_repo.create_layer("common", version="1.0")
        git_repo.create_layer("utils", version="2.0")

        # Step 2: Modify both layers in a single commit
        # Modify the uv.lock files without committing individually
        common_lock = git_repo.layers_dir / "common" / "uv.lock"
        utils_lock = git_repo.layers_dir / "utils" / "uv.lock"

        common_lock.write_text(common_lock.read_text() + "\n# Modified common\n")
        utils_lock.write_text(utils_lock.read_text() + "\n# Modified utils\n")

        # Commit both changes together
        git_repo.commit_all("Modify both common and utils layers")

        # Step 3: Run detect-changes.sh in push mode
        exit_code, output, stderr = run_detect_changes(git_repo.path, "push")

        # Step 4: Verify the output
        assert exit_code == 0, (
            f"Script failed with exit code {exit_code}, stderr: {stderr}"
        )
        assert output is not None, (
            f"Script did not produce valid JSON output, stderr: {stderr}"
        )

        # Verify layers array contains both changed layers (sorted alphabetically)
        assert sorted(output["layers"]) == ["common", "utils"], (
            f"Expected layers ['common', 'utils'], got: {output['layers']}"
        )

        # Verify matrix contains both layers with correct versions
        expected_matrix = [
            {"name": "common", "version": "1.0"},
            {"name": "utils", "version": "2.0"},
        ]
        # Sort both lists by name for comparison
        actual_matrix_sorted = sorted(output["matrix"], key=lambda x: x["name"])
        expected_matrix_sorted = sorted(expected_matrix, key=lambda x: x["name"])
        assert actual_matrix_sorted == expected_matrix_sorted, (
            f"Expected matrix {expected_matrix_sorted}, got: {actual_matrix_sorted}"
        )

        # Verify build_matrix contains entries for both layers
        build_matrix_include = output["build_matrix"]["include"]

        # Extract unique layer names from build_matrix
        build_matrix_layers = sorted(
            set(item["layer"] for item in build_matrix_include)
        )
        assert build_matrix_layers == ["common", "utils"], (
            f"Expected build_matrix to include both layers, got: {build_matrix_layers}"
        )

        # Verify each layer has the correct version in build_matrix
        for item in build_matrix_include:
            if item["layer"] == "common":
                assert item["version"] == "1.0", (
                    f"Expected common version 1.0, got: {item['version']}"
                )
            elif item["layer"] == "utils":
                assert item["version"] == "2.0", (
                    f"Expected utils version 2.0, got: {item['version']}"
                )

        # Verify has_changes is true
        assert output["has_changes"] is True, (
            f"Expected has_changes to be true, got: {output['has_changes']}"
        )


class TestDetectChangesIgnoresNonLayers:
    """Tests for ignoring non-layer path changes.

    **Validates: Requirements 1.3**

    These tests verify that changes to files outside the layers/
    directory are not reported as layer changes.
    """

    def test_detect_changes_ignores_non_layers(self, git_repo: GitRepo):
        """Test that non-layer paths are ignored.

        **Validates: Requirements 1.3**

        This test verifies that when only non-layer files are modified
        (e.g., terraform/, scripts/, README.md), the detect-changes.sh
        script returns an empty result with has_changes=false.

        Steps:
        1. Create a layer in the git repo (establishes baseline)
        2. Create/modify non-layer files (terraform/main.tf, scripts/test.sh, README.md)
        3. Run detect-changes.sh in push mode
        4. Verify the output has empty layers array and has_changes is false
        """
        # Step 1: Create a layer to establish baseline
        git_repo.create_layer("common", version="1.0")

        # Step 2: Create/modify non-layer files in a single commit
        # Create terraform/main.tf
        terraform_dir = git_repo.path / "terraform"
        terraform_dir.mkdir(parents=True, exist_ok=True)
        (terraform_dir / "main.tf").write_text(
            '# Terraform configuration\nresource "aws_lambda_layer_version" "layer" {}\n'
        )

        # Create scripts/test.sh
        scripts_dir = git_repo.path / "scripts"
        scripts_dir.mkdir(parents=True, exist_ok=True)
        (scripts_dir / "test.sh").write_text('#!/bin/bash\necho "test"\n')

        # Modify README.md
        readme_path = git_repo.path / "README.md"
        readme_path.write_text("# Updated Test Repository\n\nWith more content.\n")

        # Create a .github/workflows file
        workflows_dir = git_repo.path / ".github" / "workflows"
        workflows_dir.mkdir(parents=True, exist_ok=True)
        (workflows_dir / "ci.yml").write_text(
            "name: CI\non: push\njobs:\n  test:\n    runs-on: ubuntu-latest\n"
        )

        # Commit all non-layer changes together
        git_repo.commit_all("Add terraform, scripts, and update README")

        # Step 3: Run detect-changes.sh in push mode
        exit_code, output, stderr = run_detect_changes(git_repo.path, "push")

        # Step 4: Verify the output
        assert exit_code == 0, (
            f"Script failed with exit code {exit_code}, stderr: {stderr}"
        )
        assert output is not None, (
            f"Script did not produce valid JSON output, stderr: {stderr}"
        )

        # Verify empty layers array
        assert output["layers"] == [], (
            f"Expected empty layers array, got: {output['layers']}"
        )

        # Verify empty matrix array
        assert output["matrix"] == [], (
            f"Expected empty matrix array, got: {output['matrix']}"
        )

        # Verify empty build_matrix
        assert output["build_matrix"] == {"include": []}, (
            f"Expected empty build_matrix, got: {output['build_matrix']}"
        )

        # Verify has_changes is false
        assert output["has_changes"] is False, (
            f"Expected has_changes to be false, got: {output['has_changes']}"
        )
