resource "aws_s3_bucket" "job_ads" {
  bucket = "job-ads-analysis-${var.environment}"
}

resource "aws_s3_bucket_versioning" "job_ads" {
  bucket = aws_s3_bucket.job_ads.id

  versioning_configuration {
    status = "Disabled"
  }
}

resource "aws_s3_bucket" "job_ads_silver" {
  bucket = "job-ads-analysis-silver-${var.environment}"
}

resource "aws_s3_bucket_versioning" "job_ads_silver" {
  bucket = aws_s3_bucket.job_ads_silver.id

  versioning_configuration {
    status = "Disabled"
  }
}
