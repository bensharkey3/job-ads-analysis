import os
import sys
import json
import re
import argparse
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from html.parser import HTMLParser

import boto3

SEARCH_TERMS = ["lead data engineer"]
INITIAL_TIMESTAMP = "2026-05-20T00:00:00Z"
STATE_KEY = "state/last_run_timestamp.txt"


class _TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.texts = []
        self._capture = False
        self._depth = 0
        self._target_depth = None

    def handle_starttag(self, tag, attrs):
        classes = dict(attrs).get("class", "")
        if "adp-body" in classes:
            self._capture = True
            self._target_depth = self._depth
        if self._capture:
            self._depth += 1

    def handle_endtag(self, tag):
        if self._capture:
            self._depth -= 1
            if self._depth <= self._target_depth:
                self._capture = False

    def handle_data(self, data):
        if self._capture:
            self.texts.append(data)

    def get_text(self):
        return re.sub(r"\s{2,}", "\n", "".join(self.texts)).strip()


def search_jobs(app_id, app_key, what, where, results_per_page=5, sort_by=None):
    params = {
        "app_id": app_id,
        "app_key": app_key,
        "results_per_page": results_per_page,
        "what": what,
        "where": where,
    }
    if sort_by:
        params["sort_by"] = sort_by
    url = f"https://api.adzuna.com/v1/api/jobs/au/search/1?{urllib.parse.urlencode(params)}"
    with urllib.request.urlopen(url) as response:
        return json.loads(response.read().decode())


def scrape_description(redirect_url):
    req = urllib.request.Request(
        redirect_url,
        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as response:
            html = response.read().decode("utf-8", errors="replace")
    except Exception as e:
        print(f"    Warning: could not fetch {redirect_url}: {e}")
        return None
    parser = _TextExtractor()
    parser.feed(html)
    text = parser.get_text()
    return text if text else None


def save_to_s3(s3_client, bucket, job, date):
    key = f"{date.strftime('%Y/%m/%d')}/{job['id']}.json"
    s3_client.put_object(Bucket=bucket, Key=key, Body=json.dumps(job, indent=2), ContentType="application/json")
    return key


def save_description_to_s3(s3_client, bucket, job_id, text, date):
    key = f"{date.strftime('%Y/%m/%d')}/{job_id}_description.txt"
    s3_client.put_object(Bucket=bucket, Key=key, Body=text.encode("utf-8"), ContentType="text/plain; charset=utf-8")
    return key


def load_last_timestamp(s3_client, bucket):
    try:
        obj = s3_client.get_object(Bucket=bucket, Key=STATE_KEY)
        return obj["Body"].read().decode("utf-8").strip()
    except s3_client.exceptions.NoSuchKey:
        return INITIAL_TIMESTAMP


def save_last_timestamp(s3_client, bucket, timestamp):
    s3_client.put_object(Bucket=bucket, Key=STATE_KEY, Body=timestamp.encode("utf-8"), ContentType="text/plain")


def parse_ts(ts):
    return datetime.fromisoformat(ts.replace("Z", "+00:00"))


def fetch_results(app_id, app_key, results_per_page, sort_by=None):
    seen_ids = set()
    results = []
    for term in SEARCH_TERMS:
        for job in search_jobs(app_id, app_key, what=term, where="melbourne", results_per_page=results_per_page, sort_by=sort_by).get("results", []):
            if job["id"] not in seen_ids:
                seen_ids.add(job["id"])
                results.append(job)
    return results


def process_jobs(results, s3, bucket, date):
    for i, job in enumerate(results, 1):
        job_id = job["id"]
        title = job.get("title")
        company = job.get("company", {}).get("display_name")

        json_key = save_to_s3(s3, bucket, job, date)
        print(f"[{i}] {title} @ {company}")
        print(f"     JSON: s3://{bucket}/{json_key}")

        redirect_url = job.get("redirect_url")
        if redirect_url:
            description = scrape_description(redirect_url)
            if description:
                desc_key = save_description_to_s3(s3, bucket, job_id, description, date)
                print(f"     DESC: s3://{bucket}/{desc_key}  ({len(description)} chars)")
            else:
                print(f"     DESC: scrape failed, skipped")


def run_adhoc(app_id, app_key, s3, bucket):
    print("Mode: adhoc — fetching 5 most recent results per search term\n")
    results = fetch_results(app_id, app_key, results_per_page=5)
    print(f"Found {len(results)} job listing(s).\n")
    process_jobs(results, s3, bucket, datetime.now(timezone.utc))


def run_incremental(app_id, app_key, s3, bucket):
    last_timestamp = load_last_timestamp(s3, bucket)
    print(f"Mode: incremental — fetching jobs created after {last_timestamp}\n")

    all_results = fetch_results(app_id, app_key, results_per_page=50, sort_by="date")
    cutoff = parse_ts(last_timestamp)
    results = [job for job in all_results if parse_ts(job["created"]) > cutoff]

    print(f"Found {len(results)} new job listing(s) since {last_timestamp}.\n")

    run_ts = datetime.now(timezone.utc)
    if results:
        process_jobs(results, s3, bucket, run_ts)

    save_last_timestamp(s3, bucket, run_ts.strftime("%Y-%m-%dT%H:%M:%SZ"))
    print(f"\nTimestamp updated to {run_ts.strftime('%Y-%m-%dT%H:%M:%SZ')}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=["incremental", "adhoc"], required=True)
    args = parser.parse_args()

    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")
    bucket = os.environ.get("S3_BUCKET")

    if not app_id or not app_key:
        print("Error: ADZUNA_APP_ID and ADZUNA_APP_KEY environment variables must be set.")
        sys.exit(1)
    if not bucket:
        print("Error: S3_BUCKET environment variable must be set.")
        sys.exit(1)

    s3 = boto3.client("s3")

    if args.mode == "adhoc":
        run_adhoc(app_id, app_key, s3, bucket)
    else:
        run_incremental(app_id, app_key, s3, bucket)


def lambda_handler(event, context):
    ssm = boto3.client("ssm")
    app_id = ssm.get_parameter(Name=os.environ["SSM_APP_ID_PATH"])["Parameter"]["Value"]
    app_key = ssm.get_parameter(Name=os.environ["SSM_APP_KEY_PATH"], WithDecryption=True)["Parameter"]["Value"]
    bucket = os.environ["S3_BUCKET"]

    s3 = boto3.client("s3")
    mode = event.get("mode", "incremental")

    if mode == "adhoc":
        run_adhoc(app_id, app_key, s3, bucket)
    else:
        run_incremental(app_id, app_key, s3, bucket)


if __name__ == "__main__":
    main()
