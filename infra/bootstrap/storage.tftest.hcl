mock_provider "aws" {
  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::synthetic-storage" }
  }
  mock_data "aws_iam_openid_connect_provider" {
    defaults = { arn = "arn:aws:iam::111111111111:oidc-provider/token.actions.githubusercontent.com" }
  }
}
variables {
  aws_account_id = "111111111111"
  aws_region     = "eu-west-1"
}
run "private_versioned_storage" {
  command = apply
  assert {
    condition     = length(aws_s3_bucket.storage) == 3 && aws_s3_bucket.storage["preview"].bucket != aws_s3_bucket.storage["production"].bucket && output.backend_keys.preview != output.backend_keys.production
    error_message = "Estado y artefactos deben tener separación explícita de entornos."
  }
  assert {
    condition     = alltrue([for b in aws_s3_bucket_public_access_block.storage : b.block_public_acls && b.block_public_policy && b.ignore_public_acls && b.restrict_public_buckets]) && alltrue([for b in aws_s3_bucket_versioning.storage : b.versioning_configuration[0].status == "Enabled"])
    error_message = "Todos los buckets deben ser privados y versionados."
  }
  assert {
    condition     = alltrue([for b in aws_s3_bucket_server_side_encryption_configuration.storage : one(b.rule).apply_server_side_encryption_by_default[0].sse_algorithm == "AES256"]) && alltrue([for b in aws_s3_bucket.storage : !b.force_destroy])
    error_message = "Estado y buckets bootstrap deben estar cifrados y protegidos frente al vaciado automático."
  }
}

run "lambda_repositories_are_separated_and_retained" {
  command = apply
  assert {
    condition     = aws_ecr_repository.lambda["preview"].name == "family-planner-preview" && aws_ecr_repository.lambda["production"].name == "family-planner-production" && output.lambda_repositories.preview != output.lambda_repositories.production
    error_message = "Preview y producción deben tener repositorios ECR independientes."
  }
  assert {
    condition     = length(jsondecode(aws_ecr_lifecycle_policy.lambda["preview"].policy).rules) == 2 && aws_ecr_repository.lambda["preview"].image_scanning_configuration[0].scan_on_push
    error_message = "ECR debe escanear imágenes y retener un historial limitado."
  }
}

run "github_preview_role_is_immutable_repository_and_branch_scoped" {
  command = apply
  assert {
    condition     = aws_iam_role.github_preview.name == "family-planner-preview-github-actions" && jsondecode(aws_iam_role.github_preview.assume_role_policy).Statement[0].Condition.StringLike["token.actions.githubusercontent.com:sub"] == "repo:a10pepo@29485524/family_planner@1408456566:ref:refs/heads/main"
    error_message = "OIDC debe confiar solo en main del repositorio de Family Planner."
  }
  assert {
    condition     = jsondecode(aws_iam_role_policy.github_preview.policy).Statement[0].Resource == aws_ecr_repository.lambda["preview"].arn && !contains(jsondecode(aws_iam_role_policy.github_preview.policy).Statement[0].Action, "ecr:BatchDeleteImage")
    error_message = "El rol de CI solo debe publicar imágenes de preview."
  }
}

run "reject_project_exceeding_bucket_limit" {
  command = plan
  variables { project = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
  expect_failures = [var.project]
}
