terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }
}

provider "aws" {
  region = var.aws_region
}

variable "aws_region" {
  default = "ap-southeast-2"
}

variable "environment" {
  default = "dev"
}

resource "aws_s3_bucket" "job_ads" {
  bucket = "job-ads-analysis-${var.environment}"
}

resource "aws_s3_bucket_versioning" "job_ads" {
  bucket = aws_s3_bucket.job_ads.id

  versioning_configuration {
    status = "Disabled"
  }
}
