"""Drop the weekly files in the landing bucket, as the wholesalers would, and wait for the Lambda.

    python -m lake.upload                       # every file, week by week
    python -m lake.upload --wholesaler distrimed
"""
import argparse
import hashlib
import time

from .aws import LANDING_BUCKET, log_table, s3
from .generate import LANDING_DIR


def wait_for(key, md5, timeout=300):
    """The Lambda logs each file in DynamoDB with its ETag (the MD5 of the file)."""
    start = time.time()
    while time.time() - start < timeout:
        item = log_table.get_item(Key={"file_key": key}).get("Item")
        if item and item.get("etag") == md5:
            return item
        time.sleep(1)
    raise TimeoutError(f"no result for {key} after {timeout}s: check the DLQ with python -m lake.status")


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--wholesaler")
    args = parser.parse_args(argv)
    files = sorted(LANDING_DIR.glob(f"{args.wholesaler or '*'}/*.csv"))
    for path in files:
        key = f"landing/{path.parent.name}/{path.name}"
        md5 = hashlib.md5(path.read_bytes()).hexdigest()
        s3.upload_file(str(path), LANDING_BUCKET, key)
        item = wait_for(key, md5)
        print(f"  {key:38} {item['status']:8} rows={item['rows_in']}" + (f"  unknown={item['unknown']}" if item.get("unknown") else ""))


if __name__ == "__main__":
    main()
