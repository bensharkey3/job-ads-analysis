import json
import os

import boto3
from botocore.exceptions import ClientError

INITIAL_DATE = "2026/05/20"
STATE_KEY = "state/last_processed_date.txt"


def load_state(s3, bucket):
    try:
        obj = s3.get_object(Bucket=bucket, Key=STATE_KEY)
        return obj["Body"].read().decode().strip()
    except ClientError as e:
        if e.response["Error"]["Code"] == "NoSuchKey":
            return INITIAL_DATE
        raise


def save_state(s3, bucket, date_path):
    s3.put_object(Bucket=bucket, Key=STATE_KEY, Body=date_path.encode(), ContentType="text/plain")


def list_bronze_date_paths(s3, bucket, from_date):
    date_paths = set()
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket):
        for obj in page.get("Contents", []):
            key = obj["Key"]
            filename = key.split("/")[-1]
            # Raw job JSON only: YYYY/MM/DD/<id>.json — exclude _description.txt and _summarised.json
            if filename.endswith(".json") and "_" not in filename:
                date_path = "/".join(key.split("/")[:3])
                if date_path >= from_date:
                    date_paths.add(date_path)
    return sorted(date_paths)


def list_job_ids_for_date(s3, bucket, date_path):
    job_ids = []
    paginator = s3.get_paginator("list_objects_v2")
    for page in paginator.paginate(Bucket=bucket, Prefix=f"{date_path}/"):
        for obj in page.get("Contents", []):
            filename = obj["Key"].split("/")[-1]
            if filename.endswith(".json") and "_" not in filename:
                job_ids.append(filename[:-5])
    return job_ids


def flatten_job(job_id, job, skills=None):
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
        "skills_and_tools_summary": skills,
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


def date_path_to_filename(date_path):
    # "2026/06/04" -> "20260604.json"
    return date_path.replace("/", "") + ".json"


def lambda_handler(event, context):
    bronze_bucket = os.environ["S3_BRONZE_BUCKET"]
    silver_bucket = os.environ["S3_SILVER_BUCKET"]

    s3 = boto3.client("s3")

    from_date = load_state(s3, silver_bucket)
    print(f"Processing bronze date folders >= {from_date}")

    date_paths = list_bronze_date_paths(s3, bronze_bucket, from_date)
    if not date_paths:
        print("No date folders to process.")
        return

    print(f"Found {len(date_paths)} date folder(s): {date_paths}")

    latest_date = from_date
    for date_path in date_paths:
        job_ids = list_job_ids_for_date(s3, bronze_bucket, date_path)
        silver_key = date_path_to_filename(date_path)
        existing = load_existing(s3, silver_bucket, silver_key)

        for job_id in job_ids:
            bronze_key = f"{date_path}/{job_id}.json"
            try:
                obj = s3.get_object(Bucket=bronze_bucket, Key=bronze_key)
                job = json.loads(obj["Body"].read())
                skills = None
                try:
                    s_obj = s3.get_object(Bucket=bronze_bucket, Key=f"{date_path}/{job_id}_summarised.json")
                    skills = json.loads(s_obj["Body"].read())
                except ClientError as e:
                    if e.response["Error"]["Code"] != "NoSuchKey":
                        raise
                existing[job_id] = flatten_job(job_id, job, skills)
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
        if date_path > latest_date:
            latest_date = date_path

    save_state(s3, silver_bucket, latest_date)
    print(f"State updated to {latest_date}")
