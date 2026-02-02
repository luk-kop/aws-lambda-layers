# Usage Guide

Daily operations for managing AWS Lambda Layers.

## Create a New Layer

```bash
./scripts/create-layer.sh <name>

# Example:
./scripts/create-layer.sh utils
```

This creates:

- `layers/<name>/pyproject.toml` - Template configuration
- `layers/<name>/uv.lock` - Initial lockfile
- `layers/<name>/src/` - Directory for custom code

## Add Dependencies

```bash
cd layers/<name>
uv add requests boto3-stubs
```

If you edit `pyproject.toml` manually, regenerate the lockfile:

```bash
uv lock
```

## Add Custom Python Code

Place custom Python modules in the `src/` directory. These files are automatically included in the layer ZIP alongside installed dependencies.

```bash
# Create a custom module
cat > layers/<name>/src/utils.py << 'EOF'
def helper_function():
    return "Hello from layer"
EOF
```

The `src/` contents are copied to the `python/` directory in the ZIP, so they're importable in Lambda:

```python
# In your Lambda function
from utils import helper_function
```

Remember to bump the version when changing `src/` contents.

## Build Layer Locally

```bash
./scripts/build-layer.sh <name> <python> <arch>

# Example:
./scripts/build-layer.sh common 3.12 x86_64
```

Output: `.build/<name>/dist/py<python>-<arch>.zip`

## Add or Remove Build Variants

Build variants (Python versions and architectures) are defined in `[tool.lambda_layer]` section of `pyproject.toml`. Changing variants requires a version bump since it affects what artifacts are released.

### Add a new variant (e.g., arm64 support)

```bash
cd layers/<name>

# Edit pyproject.toml:
# 1. Add architecture to [tool.lambda_layer].architectures
# 2. Bump version

# Before:
# [tool.lambda_layer]
# python_versions = ["3.12"]
# architectures = ["x86_64"]

# After:
# [tool.lambda_layer]
# python_versions = ["3.12"]
# architectures = ["x86_64", "arm64"]

# Bump version and commit
uv lock
git add .
git commit -m "<name>: add arm64 support"
```

### Add a new Python version

```bash
cd layers/<name>

# Edit pyproject.toml:
# 1. Ensure requires-python allows the new version
# 2. Add to [tool.lambda_layer].python_versions
# 3. Bump version

# Example: add Python 3.13
# requires-python = ">=3.11"  # Already allows 3.13
# [tool.lambda_layer]
# python_versions = ["3.12", "3.13"]

uv lock
git add .
git commit -m "<name>: add Python 3.13 support"
```

### Remove a variant

Removing a variant is a breaking change - existing Lambdas using that variant will fail to deploy. Bump the major version.

```bash
cd layers/<name>

# Edit pyproject.toml:
# 1. Remove from python_versions or architectures
# 2. Bump MAJOR version (X.Y → X+1.0)

git add .
git commit -m "<name>: remove Python 3.11 support (breaking)"
```

## Release a Layer

Layers are released automatically when changes are merged to main. The CI detects which layers changed, builds all variants, uploads to S3, and creates GitHub releases.

1. Update version in `pyproject.toml`
2. Update lockfile if needed: `cd layers/<name> && uv lock`
3. Commit changes and create a pull request
4. PR validation runs automatically (lockfile check, S3 version check, build)
5. Get PR reviewed and approved
6. Merge to main - CI automatically detects changes, builds, and publishes

```bash
# Example workflow:
cd layers/common
# Edit pyproject.toml: version = "1.1"
uv lock
git add .
git commit -m "common: bump to 1.1"
git push origin feature/common-1.1
# Create PR, get review, merge
```

The release workflow will:

- Detect which layers changed in the merge commit
- Build all variants defined in `[tool.lambda_layer]`
- Upload artifacts to S3 `layers/<name>/<version>/`
- Create a GitHub Release with release notes

### GitHub Release Contents

Each release includes:

- Layer name and version
- Dependencies list from `pyproject.toml`
- Build variants (Python versions, architectures)
- Commit history since last release
- Terraform usage snippet
- S3 artifact location

Example release body:

```
## Lambda Layer Release

**Layer:** common
**Version:** 1.1

### Dependencies

- requests>=2.31
- boto3>=1.34

### Build Variants

- Python 3.12, x86_64
- Python 3.12, arm64

### Changes

- feat: add new utility function
- fix: handle edge case in parser

### Usage (Terraform)

layers = [
  { name = "common", version = "1.1", python = "312", arch = "x86_64" }
]

### S3 Artifacts

Artifacts are available at:
s3://my-lambda-layers/layers/common/1.1/
```

## Test Build on PR

Test artifacts are uploaded to S3 automatically on each push to a PR:

1. PR validation runs automatically (lockfile check, S3 version check, build)
2. Build artifacts are created for all variants
3. The `upload-test` job waits for `test-upload` environment approval
4. Approve the environment in GitHub Actions to upload artifacts
5. CI posts a comment on the PR with the Terraform snippet and expiry date

Configure the `test-upload` environment in GitHub repository settings → Environments to require reviewers.

### Example CI Comment

After successful upload, CI adds a comment to the PR:

```
✅ Test artifacts uploaded

Commit: abc123f

Use in Terraform:

test_layers = [
  { name = "common", version = "1.0", python = "312", arch = "x86_64", commit = "abc123f" }
]

⚠️ These artifacts will be automatically deleted on 2026-02-09 14:32 UTC
```

Each new push updates the comment with the new commit SHA and expiry date.

**Note:** Each commit creates a new test artifact with a unique path (`test/<name>/<version>/<commit>/...`). This ensures multiple testers can safely test different commits from the same PR without overwriting each other's artifacts. Test artifacts are automatically deleted after 7 days.

## Deploy with Terraform

```hcl
# terraform.tfvars
artifacts_bucket = "my-lambda-layers"

# Production layers (from layers/ S3 prefix)
layers = [
  { name = "common", version = "1.0", python = "312", arch = "x86_64" }
]

# Test layers (from test/<name>/<version>/<commit>/ S3 prefix) - typically empty in prod
test_layers = []
```

```bash
cd terraform
terraform init
terraform apply
```

## Deploy Test Layers (from PR)

Use the `test_layers` variable to deploy test artifacts. Copy the snippet from the CI comment on your PR:

```hcl
# terraform.tfvars - Deploy test layer from commit abc123f
layers = []

test_layers = [
  { name = "common", version = "1.0", python = "312", arch = "x86_64", commit = "abc123f" }
]
```

This allows testing layer changes in a target AWS account before merging the PR.

## Use Layer in Lambda

Reference the layer ARN from Terraform outputs:

```hcl
resource "aws_lambda_function" "example" {
  # ...
  # Production layer (note: version dot replaced with underscore)
  layers = [module.layers.layer_arns["common-v1_0-py312-x86_64"]]
}

resource "aws_lambda_function" "test_example" {
  # ...
  # Test layer
  layers = [module.layers.test_layer_arns["test-common-v1_0-abc123f-py312-x86_64"]]
}
```

## Verify Layer Deployment

After Terraform apply:

```bash
# List layer versions
aws lambda list-layer-versions --layer-name <layer-name>

# Get layer ARN from Terraform output
cd terraform
terraform output layer_arns
```

## CI Integration Examples

The `layer_config.py` script outputs CI-agnostic JSON that works with any CI system when receiving paths via stdin.

### GitHub Actions

```yaml
detect-changes:
  runs-on: ubuntu-latest
  outputs:
    matrix: ${{ steps.matrix.outputs.matrix }}
  steps:
    - uses: actions/checkout@v4
      with:
        fetch-depth: 0
    - name: Build matrix
      id: matrix
      run: |
        RESULT=$(git diff --name-only origin/main...HEAD | grep '^layers/' | python scripts/layer_config.py)
        # Wrap in {include: [...]} for GitHub Actions matrix strategy
        echo "matrix=$(echo $RESULT | jq -c '{include: .build_matrix}')" >> $GITHUB_OUTPUT

build:
  needs: detect-changes
  strategy:
    matrix: ${{ fromJson(needs.detect-changes.outputs.matrix) }}
  steps:
    - run: ./scripts/build-layer.sh ${{ matrix.layer }} ${{ matrix.python }} ${{ matrix.arch }}
```

### GitLab CI

```yaml
detect-changes:
  script:
    - RESULT=$(git diff --name-only origin/main...HEAD | grep '^layers/' | python scripts/layer_config.py)
    - echo "BUILD_MATRIX=$(echo $RESULT | jq -c '.build_matrix')" >> build.env
  artifacts:
    reports:
      dotenv: build.env

build-layer:
  needs: [detect-changes]
  parallel:
    matrix:
      - VARIANT: $BUILD_MATRIX
  script:
    - ./scripts/build-layer.sh $VARIANT_LAYER $VARIANT_PYTHON $VARIANT_ARCH
```

## Next Steps

If you encounter issues, see [Troubleshooting Guide](TROUBLESHOOTING.md).
