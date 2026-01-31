output "layer_arns" {
  description = "ARNs of the created Lambda layers (map of layer key to ARN)"
  value       = { for k, v in aws_lambda_layer_version.this : k => v.arn }
}

output "layer_versions" {
  description = "Version numbers of the created Lambda layers (map of layer key to version)"
  value       = { for k, v in aws_lambda_layer_version.this : k => v.version }
}
