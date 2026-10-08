mock_provider "aws" {
  mock_resource "aws_s3_bucket" {
    defaults = { arn = "arn:aws:s3:::synthetic-storage" }
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
    error_message = "Estado y ZIPs deben estar cifrados y protegidos frente al vaciado automático."
  }
}

run "reject_project_exceeding_bucket_limit" {
  command = plan
  variables { project = "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" }
  expect_failures = [var.project]
}
