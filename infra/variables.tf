variable "localstack" {
  description = "true: deploy to LocalStack on this computer. false: deploy to the real AWS account in your credentials."
  type        = bool
  default     = true
}

variable "localstack_endpoint" {
  type    = string
  default = "http://localhost:4566"
}

variable "region" {
  type    = string
  default = "us-east-1"
}

variable "suffix" {
  description = "Bucket names are global on AWS: pick something unique, e.g. your GitHub name."
  type        = string
  default     = "local"
}
