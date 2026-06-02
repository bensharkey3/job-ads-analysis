import os
import sys
import json
import urllib.request
import urllib.parse
from datetime import datetime, timezone

import boto3


def search_jobs(app_id, app_key, what, where, results_per_page=5):
    params = urllib.parse.urlencode({
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": results_per_page,
        "what": what,
        "where": where,
    })
    url = f"https://api.adzuna.com/v1/api/jobs/au/search/1?{params}"

    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode())


def fetch_full_description(app_id, app_key, adref):
    params = urllib.parse.urlencode({"app_id": app_id, "app_key": app_key})
    url = f"https://api.adzuna.com/v1/api/jobs/au/ad/{adref}?{params}"
    with urllib.request.urlopen(url) as response:
        data = json.loads(response.read().decode())
    return data.get("description", "")


def save_to_s3(s3_client, bucket, job, date):
    job_id = job["id"]
    key = f"{date.strftime('%Y/%m/%d')}/{job_id}.json"
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(job, indent=2),
        ContentType="application/json",
    )
    return key


def main():
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    bucket = os.environ.get("S3_BUCKET")

    if not app_id or not app_key:
        print("Error: ADZUNA_APP_ID and ADZUNA_APP_KEY environment variables must be set.")
        sys.exit(1)

    if not bucket:
        print("Error: S3_BUCKET environment variable must be set.")
        sys.exit(1)

    data = search_jobs(app_id, app_key, what="senior data engineer", where="melbourne")
    results = data.get("results", [])
    print(f"Found {len(results)} job listing(s).\n")

    s3 = boto3.client("s3")
    date = datetime.now(timezone.utc)

    for i, job in enumerate(results, 1):
        adref = job.get("adref")
        if adref:
            job["description"] = fetch_full_description(app_id, app_key, adref)
        key = save_to_s3(s3, bucket, job, date)
        print(f"[{i}] Saved s3://{bucket}/{key}  —  {job.get('title')} @ {job.get('company', {}).get('display_name')}")


if __name__ == "__main__":
    main()
