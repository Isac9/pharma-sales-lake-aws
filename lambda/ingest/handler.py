"""Lambda triggered by every file dropped in the landing bucket.

A file is loaded completely or not at all: if a single product or locality is
unknown, the whole file is rejected and an alert goes to SQS. Totals would
otherwise look plausible, just too low.
"""
import gzip
import json
import os
import urllib.parse
from datetime import datetime, timezone

import boto3
from botocore.config import Config

from formats import apply_aliases, load_aliases, parse_file, parse_key

s3 = boto3.client("s3", config=Config(s3={"addressing_style": "path"}))
sqs = boto3.client("sqs")
log_table = boto3.resource("dynamodb").Table(os.environ["LOG_TABLE"])
LAKE = os.environ["LAKE_BUCKET"]
ALERT_QUEUE_URL = os.environ["ALERT_QUEUE_URL"]


def lambda_handler(event, context):
    results = []
    for record in event["Records"]:
        obj = record["s3"]["object"]
        key = urllib.parse.unquote_plus(obj["key"])
        results.append(process(record["s3"]["bucket"]["name"], key, obj.get("eTag", "").strip('"')))
    return results


def _read(bucket, key):
    return s3.get_object(Bucket=bucket, Key=key)["Body"].read()


def _put_jsonl_gz(key, rows):
    body = "\n".join(json.dumps(r, ensure_ascii=False, default=str) for r in rows).encode()
    s3.put_object(Bucket=LAKE, Key=key, Body=gzip.compress(body), ContentEncoding="gzip")


def process(bucket, key, etag):
    previous = log_table.get_item(Key={"file_key": key}).get("Item")
    if previous and previous["status"] == "LOADED" and previous.get("etag") == etag:
        return {"file_key": key, "status": "SKIPPED"}  # same file delivered twice: idempotent

    wholesaler, week = parse_key(key)
    rows = parse_file(_read(bucket, key), wholesaler, source_file=key, file_week=week)
    products = load_aliases(_read(LAKE, "reference/product_aliases.csv").decode(), per_wholesaler=True)
    localities = load_aliases(_read(LAKE, "reference/locality_aliases.csv").decode(), per_wholesaler=False)
    good, unknown = apply_aliases(rows, products, localities)
    amount = sum(r["amount_xof"] for r in rows)

    item = {"file_key": key, "etag": etag, "wholesaler": wholesaler, "file_week": week,
            "rows_in": len(rows), "amount_xof": str(amount),
            "processed_at": datetime.now(timezone.utc).isoformat()}
    if unknown:
        _put_jsonl_gz(f"quarantine/{wholesaler}/{week}.jsonl.gz", rows)
        sqs.send_message(QueueUrl=ALERT_QUEUE_URL, MessageBody=json.dumps(
            {"file_key": key, "unknown": unknown, "action": "add the names to reference/*_aliases.csv, then re-upload"},
            ensure_ascii=False))
        item.update(status="REJECTED", rows_loaded=0, unknown=json.dumps(unknown, ensure_ascii=False))
    else:
        silver = [{**r, "amount_xof": float(r["amount_xof"])} for r in good]
        _put_jsonl_gz(f"silver/sales/{wholesaler}/{week}.jsonl.gz", silver)
        manifest = {"wholesaler": wholesaler, "file_week": week, "rows": len(rows), "amount_xof": str(amount),
                    "source_file": key}
        s3.put_object(Bucket=LAKE, Key=f"manifests/{wholesaler}/{week}.json", Body=json.dumps(manifest).encode())
        item.update(status="LOADED", rows_loaded=len(good))
    log_table.put_item(Item=item)
    return {"file_key": key, "status": item["status"]}
