import os
import sys
import json
import urllib.request
import urllib.parse


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


def main():
    app_id = os.environ.get("ADZUNA_APP_ID")
    app_key = os.environ.get("ADZUNA_APP_KEY")

    if not app_id or not app_key:
        print("Error: ADZUNA_APP_ID and ADZUNA_APP_KEY environment variables must be set.")
        sys.exit(1)

    data = search_jobs(app_id, app_key, what="senior data engineer", where="melbourne")

    results = data.get("results", [])
    print(f"Found {len(results)} job listing(s):\n")

    for i, job in enumerate(results, 1):
        print(f"--- Job {i} ---")
        print(f"Title:    {job.get('title')}")
        print(f"Company:  {job.get('company', {}).get('display_name')}")
        print(f"Location: {job.get('location', {}).get('display_name')}")
        print(f"Salary:   {job.get('salary_min')} - {job.get('salary_max')}")
        print(f"Posted:   {job.get('created')}")
        print(f"URL:      {job.get('redirect_url')}")
        print()


if __name__ == "__main__":
    main()
