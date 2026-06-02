import os
import sys
import json
import re
import urllib.request
import urllib.parse
from datetime import datetime, timezone
from html.parser import HTMLParser

import boto3


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
    job_id = job["id"]
    key = f"{date.strftime('%Y/%m/%d')}/{job_id}.json"
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=json.dumps(job, indent=2),
        ContentType="application/json",
    )
    return key


def save_description_to_s3(s3_client, bucket, job_id, text, date):
    key = f"{date.strftime('%Y/%m/%d')}/{job_id}_description.txt"
    s3_client.put_object(
        Bucket=bucket,
        Key=key,
        Body=text.encode("utf-8"),
        ContentType="text/plain; charset=utf-8",
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

    search_terms = ["senior data engineer", "lead data engineer"]
    seen_ids = set()
    results = []
    for term in search_terms:
        for job in search_jobs(app_id, app_key, what=term, where="melbourne").get("results", []):
            if job["id"] not in seen_ids:
                seen_ids.add(job["id"])
                results.append(job)
    print(f"Found {len(results)} job listing(s).\n")

    s3 = boto3.client("s3")
    date = datetime.now(timezone.utc)

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


if __name__ == "__main__":
    main()
