data "archive_file" "lambda_zip" {
  type        = "zip"
  source_file = "${path.module}/../search_jobs.py"
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

resource "aws_lambda_function" "job_ads" {
  filename         = data.archive_file.lambda_zip.output_path
  function_name    = "job-ads-${var.environment}"
  role             = aws_iam_role.lambda_exec.arn
  handler          = "search_jobs.lambda_handler"
  runtime          = "python3.12"
  source_code_hash = data.archive_file.lambda_zip.output_base64sha256
  timeout          = 300

  environment {
    variables = {
      S3_BUCKET        = aws_s3_bucket.job_ads.bucket
      SSM_APP_ID_PATH  = aws_ssm_parameter.adzuna_app_id.name
      SSM_APP_KEY_PATH = aws_ssm_parameter.adzuna_app_key.name
    }
  }
}
