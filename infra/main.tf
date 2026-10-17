terraform {
  required_version = ">= 1.6"
  required_providers {
    aws     = { source = "hashicorp/aws", version = "~> 5.80.0" }
    archive = { source = "hashicorp/archive", version = "~> 2.6" }
  }
}

# Same code for LocalStack (default) and for a real AWS account (-var localstack=false).
provider "aws" {
  region                      = var.region
  access_key                  = var.localstack ? "test" : null
  secret_key                  = var.localstack ? "test" : null
  skip_credentials_validation = var.localstack
  skip_metadata_api_check     = var.localstack
  skip_requesting_account_id  = var.localstack
  s3_use_path_style           = var.localstack

  dynamic "endpoints" {
    for_each = var.localstack ? [var.localstack_endpoint] : []
    content {
      s3             = endpoints.value
      lambda         = endpoints.value
      iam            = endpoints.value
      sts            = endpoints.value
      sqs            = endpoints.value
      dynamodb       = endpoints.value
      cloudwatchlogs = endpoints.value
    }
  }

  default_tags {
    tags = { project = "pharma-sales-lake" }
  }
}

locals {
  name = "pharma"
}

# ---------- Storage: landing zone and data lake ----------

resource "aws_s3_bucket" "landing" {
  bucket        = "${local.name}-landing-${var.suffix}"
  force_destroy = true
}

resource "aws_s3_bucket" "lake" {
  bucket        = "${local.name}-lake-${var.suffix}"
  force_destroy = true
}

resource "aws_s3_bucket_public_access_block" "all" {
  for_each                = { landing = aws_s3_bucket.landing.id, lake = aws_s3_bucket.lake.id }
  bucket                  = each.value
  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_server_side_encryption_configuration" "lake" {
  bucket = aws_s3_bucket.lake.id
  rule {
    apply_server_side_encryption_by_default { sse_algorithm = "AES256" }
  }
}

# Raw files are kept 90 days in the landing zone, then deleted.
resource "aws_s3_bucket_lifecycle_configuration" "landing" {
  bucket = aws_s3_bucket.landing.id
  rule {
    id     = "expire-raw-files"
    status = "Enabled"
    filter { prefix = "landing/" }
    expiration { days = 90 }
  }
}

resource "aws_s3_object" "reference" {
  for_each = toset(["product_aliases.csv", "locality_aliases.csv"])
  bucket   = aws_s3_bucket.lake.id
  key      = "reference/${each.key}"
  source   = "${path.module}/../reference/${each.key}"
  etag     = filemd5("${path.module}/../reference/${each.key}")
}

# ---------- Ingestion log, alerts, failures ----------

resource "aws_dynamodb_table" "ingestion_log" {
  name         = "${local.name}-ingestion-log"
  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "file_key"
  attribute {
    name = "file_key"
    type = "S"
  }
}

resource "aws_sqs_queue" "unknown_values" {
  name = "${local.name}-unknown-values"
}

resource "aws_sqs_queue" "ingest_failures" {
  name                      = "${local.name}-ingest-failures"
  message_retention_seconds = 1209600
}

# ---------- Lambda ----------

data "archive_file" "ingest" {
  type        = "zip"
  source_dir  = "${path.module}/../lambda/ingest"
  output_path = "${path.module}/build/ingest.zip"
  excludes    = ["__pycache__"]
}

resource "aws_iam_role" "ingest" {
  name = "${local.name}-ingest"
  assume_role_policy = jsonencode({
    Version   = "2012-10-17"
    Statement = [{ Effect = "Allow", Action = "sts:AssumeRole", Principal = { Service = "lambda.amazonaws.com" } }]
  })
}

# Least privilege: read the landing zone, write the lake, its own log table and queues.
resource "aws_iam_role_policy" "ingest" {
  role = aws_iam_role.ingest.id
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      { Effect = "Allow", Action = ["s3:GetObject"], Resource = "${aws_s3_bucket.landing.arn}/*" },
      { Effect = "Allow", Action = ["s3:GetObject", "s3:PutObject"], Resource = "${aws_s3_bucket.lake.arn}/*" },
      { Effect = "Allow", Action = ["dynamodb:GetItem", "dynamodb:PutItem"], Resource = aws_dynamodb_table.ingestion_log.arn },
      { Effect = "Allow", Action = ["sqs:SendMessage"], Resource = [aws_sqs_queue.unknown_values.arn, aws_sqs_queue.ingest_failures.arn] },
      { Effect = "Allow", Action = ["logs:CreateLogStream", "logs:PutLogEvents"], Resource = "${aws_cloudwatch_log_group.ingest.arn}:*" },
    ]
  })
}

resource "aws_cloudwatch_log_group" "ingest" {
  name              = "/aws/lambda/${local.name}-ingest"
  retention_in_days = 14
}

resource "aws_lambda_function" "ingest" {
  function_name    = "${local.name}-ingest"
  role             = aws_iam_role.ingest.arn
  runtime          = "python3.12"
  handler          = "handler.lambda_handler"
  filename         = data.archive_file.ingest.output_path
  source_code_hash = data.archive_file.ingest.output_base64sha256
  timeout          = 60
  memory_size      = 256
  environment {
    variables = {
      LAKE_BUCKET     = aws_s3_bucket.lake.id
      LOG_TABLE       = aws_dynamodb_table.ingestion_log.name
      ALERT_QUEUE_URL = aws_sqs_queue.unknown_values.url
    }
  }
  depends_on = [aws_cloudwatch_log_group.ingest]
}

# A crash (unreadable file, unknown wholesaler) is not retried: it goes to the failure queue.
resource "aws_lambda_function_event_invoke_config" "ingest" {
  function_name          = aws_lambda_function.ingest.function_name
  maximum_retry_attempts = 0
  destination_config {
    on_failure { destination = aws_sqs_queue.ingest_failures.arn }
  }
}

resource "aws_lambda_permission" "from_s3" {
  statement_id  = "AllowS3Invoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.ingest.function_name
  principal     = "s3.amazonaws.com"
  source_arn    = aws_s3_bucket.landing.arn
}

resource "aws_s3_bucket_notification" "landing" {
  bucket = aws_s3_bucket.landing.id
  lambda_function {
    lambda_function_arn = aws_lambda_function.ingest.arn
    events              = ["s3:ObjectCreated:*"]
    filter_prefix       = "landing/"
    filter_suffix       = ".csv"
  }
  depends_on = [aws_lambda_permission.from_s3]
}
