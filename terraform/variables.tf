variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "eu-west-1"
}

variable "project_name" {
  description = "Project name for tagging"
  type        = string
  default     = "aws-lambda-layers"
}

variable "layer_name_prefix" {
  description = "Optional prefix for Lambda layer names (e.g., 'myproject' -> 'myproject-common-v1_0-...')"
  type        = string
  default     = ""
}

variable "layers" {
  description = "List of Lambda layers to deploy"
  type = list(object({
    name    = string # e.g., "common" or "common-utils"
    version = string # e.g., "1_0" (underscore instead of dot)
    python  = string # e.g., "312" (no dot)
    arch    = string # "x86_64" or "arm64"
  }))
  default = []

  validation {
    condition = alltrue([
      for l in var.layers : can(regex("^[a-z][a-z0-9-]*$", l.name))
    ])
    error_message = "Layer name must start with lowercase letter and contain only lowercase letters, numbers, and hyphens."
  }

  validation {
    condition = alltrue([
      for l in var.layers : can(regex("^[0-9]+_[0-9]+$", l.version))
    ])
    error_message = "Layer version must be in format X_Y (e.g., '1_0', '2_1')."
  }

  validation {
    condition = alltrue([
      for l in var.layers : can(regex("^[0-9]{2,3}$", l.python))
    ])
    error_message = "Layer python must be 2-3 digits without dots (e.g., '312' for Python 3.12)."
  }

  validation {
    condition = alltrue([
      for l in var.layers : contains(["x86_64", "arm64"], l.arch)
    ])
    error_message = "Layer arch must be 'x86_64' or 'arm64'."
  }
}
