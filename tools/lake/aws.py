"""AWS clients. With AWS_ENDPOINT_URL set (docker compose does it), they talk to LocalStack."""
import os

import boto3
from botocore.config import Config

LANDING_BUCKET = os.environ.get("LANDING_BUCKET", "pharma-landing-local")
LAKE_BUCKET = os.environ.get("LAKE_BUCKET", "pharma-lake-local")
LOG_TABLE = os.environ.get("LOG_TABLE", "pharma-ingestion-log")
ALERT_QUEUE = os.environ.get("ALERT_QUEUE", "pharma-unknown-values")
DLQ = os.environ.get("DLQ", "pharma-ingest-failures")

s3 = boto3.client("s3", config=Config(s3={"addressing_style": "path"}))
sqs = boto3.client("sqs")
log_table = boto3.resource("dynamodb").Table(LOG_TABLE)
