"""What happened? The ingestion log (DynamoDB), the alerts (SQS) and the failures (DLQ)."""
import json
from collections import Counter

from .aws import ALERT_QUEUE, DLQ, log_table, sqs


def peek(queue_name):
    url = sqs.get_queue_url(QueueName=queue_name)["QueueUrl"]
    # VisibilityTimeout=0: we only look, messages stay in the queue.
    return sqs.receive_message(QueueUrl=url, MaxNumberOfMessages=10, VisibilityTimeout=0).get("Messages", [])


def main():
    items = log_table.scan()["Items"]
    print(f"Ingestion log: {len(items)} files, {dict(Counter(i['status'] for i in items))}")
    for item in sorted(items, key=lambda i: i["file_key"]):
        if item["status"] != "LOADED":
            print(f"  {item['file_key']}: {item['status']} {item.get('unknown', '')}")
    print(f"\nAlerts ({ALERT_QUEUE}):")
    for m in peek(ALERT_QUEUE):
        print("  " + json.dumps(json.loads(m["Body"]), ensure_ascii=False))
    print(f"\nLambda failures ({DLQ}): {len(peek(DLQ))} message(s)")


if __name__ == "__main__":
    main()
