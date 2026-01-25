output "layer_arns" {
  description = "ARNs of the created Lambda layers"
  value       = { for k, v in aws_lambda_layer_version.this : k => v.arn }
}

output "layer_versions" {
  description = "Version numbers of the created Lambda layers"
  value       = { for k, v in aws_lambda_layer_version.this : k => v.version }
}


output "deprecated_layers_warning" {
  description = "Warning about deprecated layers in use"
  value = length(local.deprecated_in_use) > 0 ? (
    "⚠️  DEPRECATED LAYERS IN USE:\n${join("\n", [for l, msg in local.deprecated_in_use : "  - ${l}: ${msg}"])}"
  ) : null
}
