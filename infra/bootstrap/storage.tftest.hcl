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
  assert {
    condition = alltrue([
      contains(one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Action if try(statement.Sid, "") == "ManagePreviewSiteBucket"]), "s3:GetBucketCORS"),
      contains(one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Action if try(statement.Sid, "") == "ManagePreviewSiteBucket"]), "s3:GetBucketWebsite"),
      contains(one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Action if try(statement.Sid, "") == "ManagePreviewSiteBucket"]), "s3:GetAccelerateConfiguration"),
      one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Resource if try(statement.Sid, "") == "ManagePreviewSiteBucket"]) == "arn:aws:s3:::family-planner-preview-111111111111-web",
      contains(one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Action if try(statement.Sid, "") == "ManagePreviewCredentialSecret"]), "secretsmanager:GetResourcePolicy"),
      contains(one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Action if try(statement.Sid, "") == "ReadPreviewProviderMetadata"]), "logs:DescribeLogGroups"),
      contains(one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Action if try(statement.Sid, "") == "ReadPreviewProviderMetadata"]), "cognito-idp:DescribeUserPoolDomain"),
      contains(one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Action if try(statement.Sid, "") == "ReadPreviewProviderMetadata"]), "cloudfront:ListCachePolicies"),
      contains(one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Action if try(statement.Sid, "") == "ReadPreviewCloudFrontResources"]), "cloudfront:GetFunction"),
      contains(one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Action if try(statement.Sid, "") == "ReadPreviewCloudFrontResources"]), "cloudfront:GetOriginRequestPolicy"),
      contains(one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Action if try(statement.Sid, "") == "ReadPreviewCloudFrontResources"]), "cloudfront:GetResponseHeadersPolicy"),
      one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Action if try(statement.Sid, "") == "ReadPreviewCloudFrontFunctionTags"]) == ["cloudfront:ListTagsForResource"],
      one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Resource if try(statement.Sid, "") == "ReadPreviewCloudFrontFunctionTags"]) == "arn:aws:cloudfront::111111111111:function/family-planner-preview-*",
      !contains(one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Action if try(statement.Sid, "") == "ManagePreviewData"]), "cloudfront:ListTagsForResource"),
      one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Resource if try(statement.Sid, "") == "ReadPreviewCloudFrontResources"]) == ["arn:aws:cloudfront::111111111111:function/family-planner-preview-*", "arn:aws:cloudfront::111111111111:origin-access-control/*", "arn:aws:cloudfront::111111111111:cache-policy/*", "arn:aws:cloudfront::111111111111:origin-request-policy/*", "arn:aws:cloudfront::111111111111:response-headers-policy/*"],
      one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Resource if try(statement.Sid, "") == "ManagePreviewCredentialSecret"]) == "arn:aws:secretsmanager:eu-west-1:111111111111:secret:family-planner-preview/test-account-*",
      one([for statement in jsondecode(aws_iam_role_policy.github_preview.policy).Statement : statement.Resource if try(statement.Sid, "") == "ReadPreviewProviderMetadata"]) == "*"
    ])
    error_message = "Los permisos de lectura para bucket y secreto deben quedar limitados a Preview; las consultas sin ámbito de recursos deben permanecer en un statement independiente."
  }
}

run "reject_project_exceeding_bucket_limit" {
  command = plan
  variables { project = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
  expect_failures = [var.project]
}
