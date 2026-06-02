resource "aws_ssm_parameter" "adzuna_app_id" {
  name  = "/job-ads/${var.environment}/adzuna_app_id"
  type  = "String"
  value = var.adzuna_app_id
}

resource "aws_ssm_parameter" "adzuna_app_key" {
  name  = "/job-ads/${var.environment}/adzuna_app_key"
  type  = "SecureString"
  value = var.adzuna_app_key
}
