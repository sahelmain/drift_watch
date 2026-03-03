output "ec2_public_ip" {
  description = "Public IP address of the EC2 application server"
  value       = aws_instance.app.public_ip
}

output "rds_endpoint" {
  description = "RDS PostgreSQL endpoint"
  value       = aws_db_instance.main.endpoint
}

output "redis_endpoint" {
  description = "ElastiCache Redis endpoint"
  value       = aws_elasticache_cluster.main.cache_nodes[0].address
}

output "s3_backup_bucket" {
  description = "S3 bucket name for backups"
  value       = aws_s3_bucket.backups.id
}

output "cloudwatch_log_group" {
  description = "CloudWatch log group name"
  value       = aws_cloudwatch_log_group.app.name
}

output "vpc_id" {
  description = "VPC ID"
  value       = aws_vpc.main.id
}
