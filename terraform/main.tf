locals {
  # Build production layer configs
  # layer_key: "common-v1_0-py312-x86_64" (dot replaced with underscore for AWS compatibility)
  # s3_key: "layers/common/1.0/py312-x86_64.zip"
  prod_layer_configs = {
    for l in var.layers : "${l.name}-v${replace(l.version, ".", "_")}-py${l.python}-${l.arch}" => {
      name    = l.name
      version = l.version
      python  = l.python
      arch    = l.arch
      s3_key  = "layers/${l.name}/${l.version}/py${l.python}-${l.arch}.zip"
    }
  }

  # Build test layer configs
  # layer_key: "test-42-common-v1_0-py312-x86_64" (dot replaced with underscore for AWS compatibility)
  # s3_key: "test/42/common/1.0/py312-x86_64.zip"
  test_layer_configs = {
    for l in var.test_layers : "test-${l.pr}-${l.name}-v${replace(l.version, ".", "_")}-py${l.python}-${l.arch}" => {
      name    = l.name
      version = l.version
      python  = l.python
      arch    = l.arch
      s3_key  = "test/${l.pr}/${l.name}/${l.version}/py${l.python}-${l.arch}.zip"
    }
  }

  # Merge all layer configs
  layer_configs = merge(local.prod_layer_configs, local.test_layer_configs)
}

# Verify layer artifacts exist in S3 before deployment
data "aws_s3_object" "layer" {
  for_each = local.layer_configs

  bucket = var.artifacts_bucket
  key    = each.value.s3_key

  lifecycle {
    postcondition {
      condition     = self.content_length > 0
      error_message = "Layer artifact not found or empty: s3://${var.artifacts_bucket}/${each.value.s3_key}. Ensure the layer has been built and uploaded."
    }
  }
}

resource "aws_lambda_layer_version" "this" {
  for_each = local.layer_configs

  s3_bucket = var.artifacts_bucket
  s3_key    = each.value.s3_key

  # layer_name uses the layer_key format directly (already AWS-compatible)
  layer_name = "${var.layer_name_prefix != "" ? "${var.layer_name_prefix}-" : ""}${each.key}"

  # Human-readable description
  # Transform python "312" to "3.12" by splitting: first char + "." + remaining chars
  description = "Layer ${each.value.name} v${each.value.version} (Python ${substr(each.value.python, 0, 1)}.${substr(each.value.python, 1, length(each.value.python) - 1)}, ${each.value.arch})"

  source_code_hash = data.aws_s3_object.layer[each.key].etag

  # Transform "312" to "python3.12" for Lambda runtime
  compatible_runtimes      = ["python${substr(each.value.python, 0, 1)}.${substr(each.value.python, 1, length(each.value.python) - 1)}"]
  compatible_architectures = [each.value.arch]
}
