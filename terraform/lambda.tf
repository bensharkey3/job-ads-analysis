data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/../scrape_jobs.py"
  output_path = "${path.module}/lambda.zip"
}

resource "aws_iam_role" "lambda_exec" {
  name = "job-ads-lambda-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "lambda_basic" {
  role       = aws_iam_role.lambda_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "lambda_s3" {
  name = "s3-access"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.job_ads.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.job_ads.arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "lambda_ssm" {
  name = "ssm-read"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["ssm:GetParameter"]
      Resource = [
        aws_ssm_parameter.adzuna_app_id.arn,
        aws_ssm_parameter.adzuna_app_key.arn,
      ]
    }]
  })
}

resource "aws_iam_role_policy" "lambda_invoke_summariser" {
  name = "invoke-summariser"
  role = aws_iam_role.lambda_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.job_ads_summariser.arn
    }]
  })
}

resource "aws_lambda_function" "job_ads" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "job-ads-${var.environment}"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "scrape_jobs.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 300

  environment {
    variables = {
      S3_BUCKET                = aws_s3_bucket.job_ads.bucket
      SSM_APP_ID_PATH          = aws_ssm_parameter.adzuna_app_id.name
      SSM_APP_KEY_PATH         = aws_ssm_parameter.adzuna_app_key.name
      SUMMARISER_FUNCTION_NAME = aws_lambda_function.job_ads_summariser.function_name
    }
  }
}

# ── Summariser Lambda ────────────────────────────────────────────────────────

data "archive_file" "summariser_zip" {
  type        = "zip"
  source_file = "${path.module}/../summarise_jobs.py"
  output_path = "${path.module}/summariser.zip"
}

resource "aws_iam_role" "summariser_exec" {
  name = "job-ads-summariser-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "summariser_basic" {
  role       = aws_iam_role.summariser_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "summariser_s3" {
  name = "s3-access"
  role = aws_iam_role.summariser_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.job_ads.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.job_ads.arn
      }
    ]
  })
}

resource "aws_iam_role_policy" "summariser_bedrock" {
  name = "bedrock-invoke"
  role = aws_iam_role.summariser_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "bedrock:InvokeModel"
      Resource = "arn:aws:bedrock:*::foundation-model/amazon.nova-micro-v1:0"
    }]
  })
}

resource "aws_iam_role_policy" "summariser_invoke_flattener" {
  name = "invoke-flattener"
  role = aws_iam_role.summariser_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.job_ads_flattener.arn
    }]
  })
}

resource "aws_lambda_function" "job_ads_summariser" {
  filename         = data.archive_file.summariser_zip.output_path
  function_name    = "job-ads-summariser-${var.environment}"
  role             = aws_iam_role.summariser_exec.arn
  handler          = "summarise_jobs.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.summariser_zip.output_base64sha256
  timeout          = 300

  environment {
    variables = {
      S3_BUCKET               = aws_s3_bucket.job_ads.bucket
      BEDROCK_REGION          = "us-east-1"
      FLATTENER_FUNCTION_NAME = aws_lambda_function.job_ads_flattener.function_name
    }
  }
}

# ── Flattener Lambda ─────────────────────────────────────────────────────────

data "archive_file" "flattener_zip" {
  type        = "zip"
  source_file = "${path.module}/../flatten_jobs.py"
  output_path = "${path.module}/flattener.zip"
}

resource "aws_iam_role" "flattener_exec" {
  name = "job-ads-flattener-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy_attachment" "flattener_basic" {
  role       = aws_iam_role.flattener_exec.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "flattener_s3" {
  name = "s3-access"
  role = aws_iam_role.flattener_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject"]
        Resource = "${aws_s3_bucket.job_ads.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.job_ads.arn
      },
      {
        Effect   = "Allow"
        Action   = ["s3:GetObject", "s3:PutObject"]
        Resource = "${aws_s3_bucket.job_ads_silver.arn}/*"
      },
      {
        Effect   = "Allow"
        Action   = "s3:ListBucket"
        Resource = aws_s3_bucket.job_ads_silver.arn
      }
    ]
  })
}

resource "aws_lambda_function" "job_ads_flattener" {
  filename         = data.archive_file.flattener_zip.output_path
  function_name    = "job-ads-flattener-${var.environment}"
  role             = aws_iam_role.flattener_exec.arn
  handler          = "flatten_jobs.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.flattener_zip.output_base64sha256
  timeout          = 300

  environment {
    variables = {
      S3_BRONZE_BUCKET = aws_s3_bucket.job_ads.bucket
      S3_SILVER_BUCKET = aws_s3_bucket.job_ads_silver.bucket
    }
  }
}
