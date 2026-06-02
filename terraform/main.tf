terraform {
  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
    archive = {
      source  = "hashicorp/archive"
      version = "~> 2.0"
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

variable "adzuna_app_id" {
  sensitive = true
}

variable "adzuna_app_key" {
  sensitive = true
}
