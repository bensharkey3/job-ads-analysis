resource "aws_iam_role" "scheduler_exec" {
  name = "job-ads-scheduler-${var.environment}"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Action    = "sts:AssumeRole"
      Effect    = "Allow"
      Principal = { Service = "scheduler.amazonaws.com" }
    }]
  })
}

resource "aws_iam_role_policy" "scheduler_lambda" {
  name = "invoke-lambda"
  role = aws_iam_role.scheduler_exec.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = "lambda:InvokeFunction"
      Resource = aws_lambda_function.job_ads.arn
    }]
  })
}

resource "aws_scheduler_schedule" "daily_job_ads" {
  name  = "job-ads-daily-${var.environment}"
  state = var.schedule_state

  flexible_time_window {
    mode = "OFF"
  }

  schedule_expression          = "cron(0 12 * * ? *)"
  schedule_expression_timezone = "Australia/Melbourne"

  target {
    arn      = aws_lambda_function.job_ads.arn
    role_arn = aws_iam_role.scheduler_exec.arn
    input    = jsonencode({ mode = "incremental" })
  }
}
