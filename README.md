# Job Run Steps

## Trigger

The Lambda function `job-ads-<environment>` is triggered daily at 12pm Melbourne time via EventBridge Scheduler. It can also be invoked manually via the AWS CLI or console with an optional `mode` field in the event payload.

---

## 1. Load credentials

The Lambda handler fetches credentials from AWS SSM Parameter Store:

- `ADZUNA_APP_ID` — plain text parameter
- `ADZUNA_APP_KEY` — encrypted SecureString, decrypted on retrieval

The S3 bucket name is read from the `S3_BUCKET` environment variable.

---

## 2. Determine run mode

The event payload is checked for a `mode` field. Defaults to `incremental` if not set.

| Mode | Behaviour |
|---|---|
| `incremental` | Only processes jobs newer than the last run timestamp |
| `adhoc` | Fetches the 5 most recent results per search term, regardless of timestamp |

---

## 3. Load last run timestamp (incremental only)

The file `state/last_run_timestamp.txt` is read from S3. If it does not exist, a hardcoded initial timestamp (`2026-05-25T10:39:50Z`) is used as the cutoff.

---

## 4. Fetch job listings from Adzuna API

For each search term in `SEARCH_TERMS` (currently `["lead data engineer", "senior data engineer"]`), the Adzuna API is called for jobs in Melbourne, Australia.

- **Incremental:** fetches up to 50 results sorted by date, then filters to only jobs whose `created` timestamp is after the cutoff
- **Adhoc:** fetches the 5 most recent results, no date filtering

Duplicate job IDs across search terms are deduplicated.

---

## 5. Process each new job

For each new job listing:

1. **Save JSON to S3** at `s3://<bucket>/YYYY/MM/DD/<job_id>.json` — the full API response object for that listing.
2. **Scrape the job description** by fetching the listing's `redirect_url` (the Adzuna detail page), with a 10-second timeout. The HTML is parsed to extract the text content of the `adp-body` element.
3. **Save description to S3** at `s3://<bucket>/YYYY/MM/DD/<job_id>_description.txt` if the scrape succeeded. If it failed or timed out, the description is skipped and a warning is logged.

---

## 6. Update last run timestamp (incremental only)

After all jobs are processed, the current UTC time is written back to `state/last_run_timestamp.txt` in S3. This becomes the cutoff for the next incremental run.

---

## S3 output layout

```
s3://<bucket>/
  state/
    last_run_timestamp.txt        # cutoff timestamp for incremental runs
  YYYY/
    MM/
      DD/
        <job_id>.json             # full Adzuna API response for the listing
        <job_id>_description.txt  # scraped plain-text job description
```
