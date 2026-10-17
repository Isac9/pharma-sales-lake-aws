output "landing_bucket" { value = aws_s3_bucket.landing.id }
output "lake_bucket" { value = aws_s3_bucket.lake.id }
output "ingestion_log_table" { value = aws_dynamodb_table.ingestion_log.name }
output "alert_queue_url" { value = aws_sqs_queue.unknown_values.url }
output "failure_queue_url" { value = aws_sqs_queue.ingest_failures.url }
