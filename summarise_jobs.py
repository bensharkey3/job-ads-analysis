import json
import os

import boto3

BEDROCK_MODEL_ID = "amazon.nova-micro-v1:0"

PROMPT_TEMPLATE = (
    "Extract all technical skills, tools, and technologies from the job description below. "
    "Return ONLY a JSON array of lowercase strings, no duplicates, no explanation. "
    'Example: ["python","dbt","snowflake"]\n\nJob description:\n{text}'
)


def extract_skills(bedrock, description_text):
    body = json.dumps({
        "messages": [{"role": "user", "content": PROMPT_TEMPLATE.format(text=description_text)}],
        "inferenceConfig": {"maxTokens": 512, "temperature": 0},
    })
    response = bedrock.invoke_model(modelId=BEDROCK_MODEL_ID, body=body, contentType="application/json")
    content = json.loads(response["body"].read())
    text = content["output"]["message"]["content"][0]["text"].strip()
    # Strip markdown code fences if the model wraps the JSON
    if text.startswith("```"):
        text = text.split("```")[1]
        if text.startswith("json"):
            text = text[4:]
    return json.loads(text.strip())


def summarise_key(s3, bedrock, bucket, description_key):
    obj = s3.get_object(Bucket=bucket, Key=description_key)
    description_text = obj["Body"].read().decode("utf-8")

    skills = extract_skills(bedrock, description_text)

    # 2026/06/04/5744968263_description.txt -> 2026/06/04/5744968263_summarised.json
    summarised_key = description_key.replace("_description.txt", "_summarised.json")
    s3.put_object(
        Bucket=bucket,
        Key=summarised_key,
        Body=json.dumps(skills).encode("utf-8"),
        ContentType="application/json",
    )
    print(f"  SKILLS: s3://{bucket}/{summarised_key}  {skills}")


def lambda_handler(event, context):
    description_keys = event.get("description_keys", [])
    if not description_keys:
        print("No description keys provided — nothing to summarise.")
        return

    bucket = os.environ["S3_BUCKET"]
    bedrock_region = os.environ.get("BEDROCK_REGION", "us-east-1")

    s3 = boto3.client("s3")
    bedrock = boto3.client("bedrock-runtime", region_name=bedrock_region)

    print(f"Summarising {len(description_keys)} description(s) via Bedrock ({BEDROCK_MODEL_ID})")
    for key in description_keys:
        try:
            summarise_key(s3, bedrock, bucket, key)
        except Exception as e:
            print(f"  WARNING: failed to summarise {key}: {e}")
