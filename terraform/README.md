# terraform

<!-- BEGIN_TF_DOCS -->
## Requirements

| Name | Version |
|------|---------|
| <a name="requirement_terraform"></a> [terraform](#requirement\_terraform) | >= 1.12.1 |
| <a name="requirement_aws"></a> [aws](#requirement\_aws) | ~> 6.0 |

## Providers

| Name | Version |
|------|---------|
| <a name="provider_aws"></a> [aws](#provider\_aws) | ~> 6.0 |

## Modules

No modules.

## Resources

| Name | Type |
|------|------|
| [aws_lambda_layer_version.this](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/resources/lambda_layer_version) | resource |
| [aws_s3_object.layer](https://registry.terraform.io/providers/hashicorp/aws/latest/docs/data-sources/s3_object) | data source |

## Inputs

| Name | Description | Type | Default | Required |
|------|-------------|------|---------|:--------:|
| <a name="input_artifacts_bucket"></a> [artifacts\_bucket](#input\_artifacts\_bucket) | S3 bucket name for layer artifacts (shared account) | `string` | n/a | yes |
| <a name="input_aws_region"></a> [aws\_region](#input\_aws\_region) | AWS region | `string` | `"eu-west-1"` | no |
| <a name="input_layer_name_prefix"></a> [layer\_name\_prefix](#input\_layer\_name\_prefix) | Optional prefix for Lambda layer names (e.g., 'myproject' -> 'myproject-common-v1\_0-...') | `string` | `""` | no |
| <a name="input_layers"></a> [layers](#input\_layers) | List of Lambda layers to deploy | <pre>list(object({<br/>    name      = string                     # e.g., "common" or "common-utils"<br/>    version   = string                     # e.g., "1.0" (dot notation for flat structure)<br/>    python    = string                     # e.g., "312" (no dot)<br/>    arch      = string                     # "x86_64" or "arm64"<br/>    s3_prefix = optional(string, "layers") # S3 key prefix (default: "layers", use "test/<pr-num>" for test builds)<br/>  }))</pre> | `[]` | no |
| <a name="input_project_name"></a> [project\_name](#input\_project\_name) | Project name for tagging | `string` | `"aws-lambda-layers"` | no |

## Outputs

| Name | Description |
|------|-------------|
| <a name="output_layer_arns"></a> [layer\_arns](#output\_layer\_arns) | ARNs of the created Lambda layers (map of layer key to ARN) |
| <a name="output_layer_versions"></a> [layer\_versions](#output\_layer\_versions) | Version numbers of the created Lambda layers (map of layer key to version) |
<!-- END_TF_DOCS -->
