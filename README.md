# AWS Lambda Layers

AWS Lambda layers managed with uv and Terraform.

## Project Structure

```text
aws-lambda-layers/
├── layers/
│   └── <name>/
│       └── v<version>/        # e.g., v1_0
│           └── py<python>/    # e.g., py312
│               └── <arch>/
│                   ├── pyproject.toml
│                   ├── uv.lock
│                   └── src/   # optional custom code
├── scripts/
│   ├── create-layer.sh
│   ├── build-layer.sh
│   └── build-all-layers.sh
└── terraform/
    ├── main.tf
    ├── variables.tf
    ├── outputs.tf
    └── terraform.tfvars
```

## Naming Convention

| Element | Format | Example |
| ------- | ------ | ------- |
| tfvars | `{ name, version, python, arch }` | `{ name="common", version="1_0", python="312", arch="x86_64" }` |
| Path | `{name}/v{version}/py{python}/{arch}/` | `layers/common/v1_0/py312/x86_64/` |
| Lambda name | `{name}-v{version}-py{python}-{arch}` | `common-v1_0-py312-x86_64` |
| pyproject.toml | PEP 440 standard | `version = "1.0"`, `requires-python = "==3.12.*"` |

### Value transformations

| Path/tfvars | pyproject.toml | Transformation |
| ----------- | -------------- | -------------- |
| `version = "1_0"` | `version = "1.0"` | `1_0` -> `1.0` (replace `_` with `.`) |
| `python = "312"` | `requires-python = "==3.12.*"` | `312` -> `3.12` (insert `.` after first digit) |

## Layer Configuration

Each layer requires:
- `pyproject.toml` - with values matching the path (after transformation)
- `uv.lock` - lockfile that pins exact dependency versions (required for builds)

```toml
# layers/common/v1_0/py312/x86_64/pyproject.toml
[project]
name = "common"              # must match path
version = "1.0"              # path v1_0 -> 1.0
requires-python = "==3.12.*" # path py312 -> 3.12
dependencies = []
```

The `uv.lock` file is created automatically when you run `uv add` or manually with `uv lock`.

## Versioning

Layers use X.Y versioning with Python version and architecture:

```text
layers/
└── common/
    ├── v1_0/
    │   └── py312/
    │       ├── x86_64/    # Intel/AMD Lambda
    │       └── arm64/     # Graviton Lambda
    ├── v1_1/              # minor - backwards compatible
    └── v2_0/              # major - breaking changes
```

| Change | Version | Reason |
| ------ | ------- | ------ |
| Patch dep update (2.28.1 -> 2.28.2) | keep | No API change |
| Minor dep update (2.28 -> 2.31) | Y + 1 | New features available |
| Add new dependency | Y + 1 | New features available |
| Major dep update (1.x -> 2.x) | X + 1 | API may break |
| Remove dependency | X + 1 | Code using it will break |
| Python version change | X + 1 | Create new path |

## CI Validation

CI pipeline enforces:

- **Lockfile validity** - `pyproject.toml` syntax and `uv.lock` is up-to-date
- **Config consistency** - `pyproject.toml` values (name, version, requires-python) must match directory path after transformation
- **Immutability** - existing layer paths cannot be modified, only new versions can be added

Build script also validates config consistency locally before build.

### Local validation

Validate all layers before committing:

```bash
# Validate single layer
uv lock --check --directory layers/common/v1_0/py312/x86_64

# Validate all layers
for dir in $(find layers -name "pyproject.toml" -exec dirname {} \;); do
  uv lock --check --directory "$dir"
done
```

### Pre-commit hook

Install pre-commit hooks to run validation automatically:

```bash
pip install pre-commit
pre-commit install
```

---

## Procedures

### Create a new layer

```bash
./scripts/create-layer.sh <name> <version> <python> <arch>

# Example:
./scripts/create-layer.sh common 1_0 312 x86_64
```

### Add dependencies

```bash
cd layers/common/v1_0/py312/x86_64
uv add requests boto3-stubs  # creates/updates uv.lock automatically
```

If you edit `pyproject.toml` manually, regenerate the lockfile:

```bash
uv lock
```

### Build layers

```bash
# Build single layer
./scripts/build-layer.sh common/v1_0/py312/x86_64

# Build all layers
./scripts/build-all-layers.sh
```

### Deploy with Terraform

```bash
cd terraform
cp terraform.tfvars.example terraform.tfvars
# edit terraform.tfvars
terraform init
terraform apply
```

**terraform.tfvars format:**

```hcl
aws_region        = "eu-west-1"
project_name      = "my-project"
layer_name_prefix = ""  # optional, e.g., "myapp" -> "myapp-common-v1_0-..."

# Layer format: object with { name, version, python, arch }
# Maps to path: layers/{name}/v{version}/py{python}/{arch}/
# Lambda name: {name}-v{version}-py{python}-{arch}
layers = [
  { name = "common", version = "1_0", python = "312", arch = "x86_64" },
]
```

**[AWS Lambda layer naming constraints](https://docs.aws.amazon.com/lambda/latest/api/API_PublishLayerVersion.html#API_PublishLayerVersion_RequestSyntax):**

- Length: 1-140 characters
- Allowed characters: `[a-zA-Z0-9-_]+` (alphanumeric, hyphens, underscores only)
- No dots allowed - that's why version uses `1_0` instead of `1.0`

Deployed name format: `[{layer_name_prefix}-]{name}-v{version}-py{python}-{arch}`

Examples:

- Without prefix: `common-v1_0-py312-x86_64`
- With prefix `myapp`: `myapp-common-v1_0-py312-x86_64`

### Use layer in Lambda

Reference the layer ARN from Terraform outputs:

```hcl
# If Lambda is in the same Terraform configuration:
resource "aws_lambda_function" "example" {
  # ...
  layers = [aws_lambda_layer_version.this["common-v1_0-py312-x86_64"].arn]
}

# If Lambda is in a different configuration, use the output:
# layers = ["arn:aws:lambda:eu-west-1:123456789:layer:common-v1_0-py312-x86_64:1"]
```
