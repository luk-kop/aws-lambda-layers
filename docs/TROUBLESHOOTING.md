# Troubleshooting Guide

Common issues and solutions for AWS Lambda Layers.

## Missing Artifact in S3

If Terraform fails with `NoSuchKey` error:

```bash
# Check if all artifacts exist for a version
python scripts/layer_s3.py check <name> <version> <bucket>

# Example:
python scripts/layer_s3.py check common 1.0 my-lambda-layers
```

### Scenario 1: CI release failed after merge to main

1. Go to GitHub Actions → Release Layers workflow
2. Find the failed run
3. Click "Re-run all jobs"

Note: Re-running will fail if artifacts already exist in S3 (immutability check).

### Scenario 2: Need to rebuild with updated dependencies

Since layers are released automatically on merge to main, create a new version:

```bash
# Update version in pyproject.toml
cd layers/<name>
# Edit pyproject.toml: version = "X.Y+1"

# Update lockfile
uv lock

# Commit and push via PR
git add .
git commit -m "<name>: bump to X.Y+1"
git push origin feature/<name>-bump
# Create PR → merge → CI builds and publishes automatically
```

## Re-running Failed CI Build

If CI build failed due to transient error:

1. Go to GitHub Actions → Release Layers workflow
2. Find the failed run
3. Click "Re-run all jobs"

Note: Re-running will fail if artifacts already exist in S3 (immutability check).

## Lockfile Out of Date

If validation fails with lockfile error:

```bash
cd layers/<name>
uv lock
git add uv.lock
git commit -m "<name>: update lockfile"
```

## Python Version Not Allowed

If validation fails with Python version error, ensure `python_versions` in `[tool.lambda_layer]` are allowed by `requires-python`:

```toml
# Wrong: 3.10 not allowed by >=3.11
requires-python = ">=3.11"
[tool.lambda_layer]
python_versions = ["3.10", "3.12"]  # Error!

# Correct
requires-python = ">=3.11"
[tool.lambda_layer]
python_versions = ["3.11", "3.12"]  # OK
```

## Version Already Exists in S3

If PR validation fails with "version already exists" error:

1. The version in `pyproject.toml` has already been released
2. Bump the version to a new value
3. Run `uv lock` to update the lockfile
4. Commit and push

```bash
cd layers/<name>
# Edit pyproject.toml: version = "X.Y+1"
uv lock
git add .
git commit -m "<name>: bump version"
git push
```

## Build Fails Locally

If `build-layer.sh` fails:

1. Ensure uv is installed: `uv --version`
2. Ensure Python version is available: `python3.12 --version`
3. Check the layer has valid configuration:

```bash
python scripts/layer_config.py validate layers/<name>
```

## Terraform Can't Find Layer

If Terraform fails to find the layer artifact:

1. Verify the S3 key format matches: `layers/<name>/<version>/py<python>-<arch>.zip`
2. Check the bucket name is correct in `terraform.tfvars`
3. Verify AWS credentials have read access to the bucket

```bash
# Check if artifact exists
aws s3 ls s3://<bucket>/layers/<name>/<version>/
```

## Layer ARN Not in Terraform Output

If the layer ARN is missing from `terraform output layer_arns`:

1. Ensure the layer is defined in `terraform.tfvars`
2. Run `terraform apply` to create the layer
3. Check the layer key format: `<name>-v<version>-py<python>-<arch>`

```bash
cd terraform
terraform output layer_arns
```

## GitHub Actions OIDC Authentication Fails

If CI fails with authentication errors:

1. Verify the IAM role trust policy allows the repository
2. Check the role ARN in repository variables matches the IAM role
3. Ensure the OIDC provider is configured correctly

See [Setup Guide - OIDC Authentication](SETUP.md#oidc-authentication-setup) for configuration details.

## Test Artifacts Not Uploaded

If test artifacts are not appearing in S3:

1. Check if the `test-upload` environment requires approval
2. Go to GitHub Actions and approve the pending deployment
3. Verify the `LAMBDA_LAYERS_BUCKET` variable is set correctly

## Pre-commit Hook Fails

If pre-commit hooks fail:

```bash
# Update hooks
pre-commit autoupdate

# Run manually to see detailed errors
pre-commit run --all-files

# Skip hooks temporarily (not recommended)
git commit --no-verify -m "message"
```
