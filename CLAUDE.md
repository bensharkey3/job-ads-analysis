# CLAUDE.md

## What this project does
Scrapes job ads Adzuna API and writes JSON files to S3. Runs as an AWS Lambda function triggered by EventBridge Scheduler every day. The purpose is to create data that can be analysed later.

## Priorities
- Minimise AWS costs.
- Prefer simple, serverless, pay per use AWS services.
- Prefer AWS free tier eligible services where suitable.


## Allowed technologies
- Preference for SQL and Python.
- Use Terraform for infrastructure as code.
- Use AWS as cloud provider.

## Engineering rules
- Jobs should be idempotent.
- Never hardcode secrets, tokens or passwords.
- Keep code and architecture simple.

## Git workflow
- After completing any code change, always create a new branch, commit the changes, and raise a PR without waiting to be asked.
- Do not commit directly to main branch.
