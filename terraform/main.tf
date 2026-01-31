locals {
  # Build layer configs from objects
  # layer_key: "common-v1.0-py312-x86_64"
  # s3_key: "<s3_prefix>/common/1.0/py312-x86_64.zip"
  layer_configs = {
    for l in var.layers : "${l.name}-v${l.version}-py${l.python}-${l.arch}" => {
      name      = l.name
      version   = l.version
      python    = l.python
      arch      = l.arch
      s3_prefix = l.s3_prefix
      s3_key    = "${l.s3_prefix}/${l.name}/${l.version}/py${l.python}-${l.arch}.zip"
    }
  }
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
  description = "Layer ${each.value.name} v${each.value.version} (Python ${join(".", [substr(each.value.python, 0, 1), substr(each.value.python, 1, -1)])}, ${each.value.arch})"

  source_code_hash = data.aws_s3_object.layer[each.key].etag

  # Transform "312" to "python3.12"
  compatible_runtimes      = ["python${join(".", [substr(each.value.python, 0, 1), substr(each.value.python, 1, -1)])}"]
  compatible_architectures = [each.value.arch]
}
