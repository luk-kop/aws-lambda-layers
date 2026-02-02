# Production layer outputs
output "layer_arns" {
  description = "ARNs of production Lambda layers"
  value       = { for k, v in aws_lambda_layer_version.this : k => v.arn if !startswith(k, "test-") }
}

output "layer_versions" {
  description = "Version numbers of production Lambda layers"
  value       = { for k, v in aws_lambda_layer_version.this : k => v.version if !startswith(k, "test-") }
}

# Test layer outputs
output "test_layer_arns" {
  description = "ARNs of test Lambda layers"
  value       = { for k, v in aws_lambda_layer_version.this : k => v.arn if startswith(k, "test-") }
}

output "test_layer_versions" {
  description = "Version numbers of test Lambda layers"
  value       = { for k, v in aws_lambda_layer_version.this : k => v.version if startswith(k, "test-") }
}

# All layers combined
output "all_layer_arns" {
  description = "ARNs of all Lambda layers (production and test)"
  value       = { for k, v in aws_lambda_layer_version.this : k => v.arn }
}

output "all_layer_versions" {
  description = "Version numbers of all Lambda layers (production and test)"
  value       = { for k, v in aws_lambda_layer_version.this : k => v.version }
}
