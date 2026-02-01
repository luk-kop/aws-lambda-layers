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

## Test Build on PR (Manual)

Test artifacts can be uploaded to S3 for testing before merging, but requires manual approval:

1. PR validation runs automatically (lockfile check, S3 version check, build)
2. Build artifacts are created for all variants
3. The `upload-test` job waits for `test-upload` environment approval
4. Approve the environment in GitHub Actions to upload artifacts to `test/<pr-number>/` in S3

Configure the `test-upload` environment in GitHub repository settings → Environments to require reviewers.

## Deploy with Terraform

```hcl
# terraform.tfvars
artifacts_bucket = "my-lambda-layers"

layers = [
  { name = "common", version = "1.0", python = "312", arch = "x86_64" }
]
```

```bash
cd terraform
terraform init
terraform apply
```

## Deploy Test Layers (from PR)

Use the `s3_prefix` parameter to deploy test artifacts:

```hcl
# terraform.tfvars - Deploy test layer from PR #123
layers = [
  {
    name      = "common"
    version   = "1.0"
    python    = "312"
    arch      = "x86_64"
    s3_prefix = "test/123"  # Points to test artifacts
  }
]
```

This allows testing layer changes in a target AWS account before merging the PR.

## Use Layer in Lambda

Reference the layer ARN from Terraform outputs:

```hcl
resource "aws_lambda_function" "example" {
  # ...
  layers = [module.layers.layer_arns["common-v1.0-py312-x86_64"]]
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

## Next Steps

If you encounter issues, see [Troubleshooting Guide](TROUBLESHOOTING.md).
