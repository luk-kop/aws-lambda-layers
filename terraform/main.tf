locals {
  # Build layer configs from objects
  # layer_key: "common-v1_0-py312-x86_64"
  # path: "common/v1_0/py312/x86_64"
  layer_configs = {
    for l in var.layers : "${l.name}-v${l.version}-py${l.python}-${l.arch}" => {
      name    = l.name
      version = l.version
      python  = l.python
      arch    = l.arch
      path    = "${l.name}/v${l.version}/py${l.python}/${l.arch}"
    }
  }

  # Detect deprecated layers (those with DEPRECATED file)
  deprecated_in_use = {
    for l, cfg in local.layer_configs : l => trimspace(file("${path.module}/../layers/${cfg.path}/DEPRECATED"))
    if fileexists("${path.module}/../layers/${cfg.path}/DEPRECATED")
  }
}

check "no_deprecated_layers" {
  assert {
    condition     = length(local.deprecated_in_use) == 0
    error_message = "Using deprecated layers:\n${join("\n", [for l, msg in local.deprecated_in_use : "  - ${l}: ${msg}"])}"
  }
}

resource "terraform_data" "build_layer" {
  for_each = local.layer_configs

  triggers_replace = {
    # Expected hash from source uv.lock
    lock_hash = filesha256("${path.module}/../layers/${each.value.path}/uv.lock")
    # Actual hash from build marker - if .build is deleted, this becomes "missing" and triggers rebuild
    build_marker = try(
      file("${path.module}/.build/${each.key}/.buildinfo"),
      "missing"
    )
  }

  lifecycle {
    precondition {
      condition     = fileexists("${path.module}/../layers/${each.value.path}/pyproject.toml")
      error_message = "Layer '${each.key}' not found at layers/${each.value.path}/"
    }
  }

  provisioner "local-exec" {
    command     = "./build-layer.sh ${each.value.path}"
    working_dir = "${path.module}/../scripts"
  }
}

data "archive_file" "layer" {
  for_each = local.layer_configs

  type        = "zip"
  source_dir  = "${path.module}/.build/${each.key}"
  output_path = "${path.module}/.build/${each.key}.zip"

  depends_on = [terraform_data.build_layer]
}

resource "aws_lambda_layer_version" "this" {
  for_each = local.layer_configs

  # layer_name uses the layer_key format directly (already AWS-compatible)
  layer_name = "${var.layer_name_prefix != "" ? "${var.layer_name_prefix}-" : ""}${each.key}"
  # Human-readable description: "1_0" -> "1.0", "312" -> "3.12"
  description = "Layer ${each.value.name} v${replace(each.value.version, "_", ".")} (Python ${join(".", [substr(each.value.python, 0, 1), substr(each.value.python, 1, -1)])}, ${each.value.arch})"
  filename                 = data.archive_file.layer[each.key].output_path
  source_code_hash         = data.archive_file.layer[each.key].output_base64sha256
  # Transform "312" to "python3.12"
  compatible_runtimes      = ["python${join(".", [substr(each.value.python, 0, 1), substr(each.value.python, 1, -1)])}"]
  compatible_architectures = [each.value.arch]
}
