import json
import os
from collections import defaultdict

import boto3
from botocore.exceptions import ClientError


def parse_description_key(key):
    # "2026/06/04/5744968263_description.txt" -> ("2026/06/04", "5744968263")
    parts = key.rsplit("/", 1)
    date_path = parts[0]
    filename = parts[1]
    job_id = filename.replace("_description.txt", "")
    return date_path, job_id


def date_path_to_filename(date_path):
    # "2026/06/04" -> "20260604.json"
    return date_path.replace("/", "") + ".json"


def flatten_job(job_id, job):
    company = job.get("company") or {}
    return {
        "job_id": job_id,
        "created": job.get("created"),
        "company_display_name": company.get("display_name"),
        "title": job.get("title"),
        "contract_time": job.get("contract_time"),
        "salary_max": job.get("salary_max"),
        "salary_min": job.get("salary_min"),
        "salary_is_predicted": job.get("salary_is_predicted"),
    }


def load_existing(s3, bucket, key):
    try:
        obj = s3.get_object(Bucket=bucket, Key=key)
        records = json.loads(obj["Body"].read())
        return {r["job_id"]: r for r in records}
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return {}
        raise


def lambda_handler(event, context):
    description_keys = event.get("description_keys", [])
    if not description_keys:
        print("No description keys provided — nothing to flatten.")
        return

    bronze_bucket = os.environ["S3_BRONZE_BUCKET"]
    silver_bucket = os.environ["S3_SILVER_BUCKET"]

    s3 = boto3.client("s3")

    # Group keys by date path
    by_date = defaultdict(list)
    for key in description_keys:
        date_path, job_id = parse_description_key(key)
        by_date[date_path].append(job_id)

    for date_path, job_ids in by_date.items():
        silver_key = date_path_to_filename(date_path)

        # Load any records already written for this date (idempotent merge)
        existing = load_existing(s3, silver_bucket, silver_key)

        for job_id in job_ids:
            bronze_key = f"{date_path}/{job_id}.json"
            try:
                obj = s3.get_object(Bucket=bronze_bucket, Key=bronze_key)
                job = json.loads(obj["Body"].read())
                existing[job_id] = flatten_job(job_id, job)
                print(f"  FLAT: {bronze_key}")
            except Exception as e:
                print(f"  WARNING: failed to flatten {bronze_key}: {e}")

        records = list(existing.values())
        s3.put_object(
            Bucket=silver_bucket,
            Key=silver_key,
            Body=json.dumps(records, indent=2).encode("utf-8"),
            ContentType="application/json",
        )
        print(f"Written {len(records)} record(s) to s3://{silver_bucket}/{silver_key}")
