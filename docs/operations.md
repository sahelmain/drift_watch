# DriftWatch Operations Runbook

This runbook assumes the managed production path is Vercel + Render. Later sections still include optional self-hosted reference material for teams operating their own infrastructure.

## Table of Contents

- [Deployment Procedures](#deployment-procedures)
- [Monitoring and Alerting](#monitoring-and-alerting)
- [Backup and Recovery](#backup-and-recovery)
- [Scaling Guidelines](#scaling-guidelines)
- [Troubleshooting](#troubleshooting)
- [Incident Response](#incident-response)
- [SLO Definitions](#slo-definitions)
- [Maintenance Windows](#maintenance-windows)

---

## Deployment Procedures

### Docker Compose (Local / Single-server)

```bash
# Pull latest changes
git pull origin main

# Build and restart services
docker compose build
docker compose up -d

# Run database migrations
docker compose exec api alembic upgrade head

# Verify services
docker compose ps
curl http://localhost:8000/api/health
```

### Render + Vercel (Production)

```bash
# 1. Verify CI passed for the commit that will be merged to main.
# 2. Merge to main; Vercel and Render auto-deploy from the repo connection.
# 3. Confirm the Render API pre-deploy step ran:
#    python -m pip install -r backend/requirements.txt && cd backend && alembic upgrade head
# 4. Check the API health endpoint.
curl https://driftwatch-api.onrender.com/api/health

# 5. Trigger a manual run and verify it appears in the UI/API.
# 6. Wait for the next Render cron tick and confirm each scheduled suite ran once.
```

**Required production configuration**

- Create a shared Render environment group and attach it to the API, worker, and cron services.
- Set `SECRET_KEY` in that shared group before the first production deploy.
- Keep `AUTO_CREATE_SCHEMA=false` on all backend services.
- Keep `ENABLE_INLINE_SCHEDULER=false` on the API service so Render Cron remains the only scheduler.
- Keep `VITE_ENABLE_DEMO_AUTO_LOGIN=false` in the Vercel production environment.

---

## Monitoring and Alerting

### Prometheus Metrics

The API exposes Prometheus metrics at `/api/metrics`. Key metrics:

| Metric | Type | Description |
|--------|------|-------------|
| `driftwatch_http_requests_total` | Counter | Total HTTP requests by method, path, status |
| `driftwatch_http_request_duration_seconds` | Histogram | Request latency distribution |
| `driftwatch_evaluation_runs_total` | Counter | Total evaluation runs by status |
| `driftwatch_evaluation_duration_seconds` | Histogram | Evaluation execution time |
| `driftwatch_drift_detected_total` | Counter | Number of drift detections |
| `driftwatch_celery_tasks_total` | Counter | Celery tasks by name and status |
| `driftwatch_active_workers` | Gauge | Currently active Celery workers |

### Grafana Dashboards

Access Grafana at `http://localhost:3001` (default: admin/admin).

Recommended dashboards:

1. **API Overview** — request rate, latency percentiles, error rate
2. **Evaluations** — runs per hour, success rate, average duration
3. **Drift Detection** — drift events timeline, affected suites
4. **Workers** — task throughput, queue depth, failure rate
5. **Infrastructure** — CPU, memory, disk, network

### CloudWatch Alarms (AWS)

| Alarm | Metric | Threshold | Action |
|-------|--------|-----------|--------|
| CPU High | EC2 CPUUtilization | > 80% for 15m | SNS alert |
| API 5xx | Custom 5xxErrorRate | > 10 in 5m | SNS alert |
| Disk Space | DiskSpaceUtilization | > 85% | SNS alert |
| RDS CPU | RDS CPUUtilization | > 70% for 10m | SNS alert |
| RDS Storage | FreeStorageSpace | < 5 GB | SNS alert |

### Alert Routing

Route alerts into a shared incident channel and on-call targets. Recommended destinations:

- Email notifications for on-call engineers
- Slack webhook for `#driftwatch-alerts` channel
- PagerDuty integration for P1 incidents

---

## Backup and Recovery

### Database Backups

**Automated (RDS):**

- RDS automated backups: 7-day retention, daily at 03:00 UTC
- Point-in-time recovery available within the retention window

**Manual backup to S3:**

```bash
# From EC2 instance
pg_dump -h $RDS_ENDPOINT -U driftwatch -Fc driftwatch > backup_$(date +%Y%m%d).dump
aws s3 cp backup_$(date +%Y%m%d).dump s3://driftwatch-backups/db/

# Docker Compose local
docker compose exec db pg_dump -U driftwatch -Fc driftwatch > backup.dump
```

**Scheduled backup (add to crontab):**

```bash
0 3 * * * /opt/driftwatch/scripts/backup-db.sh
```

### Restore Procedure

```bash
# From S3
aws s3 cp s3://driftwatch-backups/db/backup_20260301.dump .
pg_restore -h $RDS_ENDPOINT -U driftwatch -d driftwatch --clean backup_20260301.dump

# Docker Compose local
docker compose exec -T db pg_restore -U driftwatch -d driftwatch --clean < backup.dump
```

### Redis Data

Redis is used as a transient broker/cache. No backup required — data is regenerated on restart. For persistent task results, ensure `CELERY_RESULT_BACKEND` writes to PostgreSQL in production.

---

## Scaling Guidelines

### Horizontal Scaling: API

**Docker Compose:**

```bash
docker compose up -d --scale api=3
```

**Kubernetes:**

The HPA auto-scales API pods between 2 and 10 replicas based on CPU utilization (target: 70%).

Manual override:

```bash
kubectl -n driftwatch scale deployment/driftwatch-api --replicas=5
```

### Horizontal Scaling: Workers

Workers are the primary compute bottleneck during evaluations.

**Docker Compose:**

```bash
docker compose up -d --scale worker=4
```

**Kubernetes:**

```bash
kubectl -n driftwatch scale deployment/driftwatch-worker --replicas=6
```

**Tuning concurrency:**

Each worker runs with `--concurrency=4` by default. Adjust based on workload:

- CPU-bound evaluations: concurrency = CPU cores
- I/O-bound (waiting on LLM APIs): concurrency = 8-16

### Vertical Scaling: Database

- **RDS**: Modify instance class via Terraform (`db.t3.micro` -> `db.t3.medium` -> `db.r6g.large`)
- **Read replicas**: Add for dashboard read-heavy queries

```hcl
# In variables.tf, update:
variable "rds_instance_class" {
  default = "db.t3.medium"
}
```

### Scaling Thresholds

| Metric | Action | Target |
|--------|--------|--------|
| API latency P99 > 2s | Scale API pods | < 500ms P99 |
| Worker queue depth > 100 | Scale workers | Queue depth < 10 |
| DB connections > 80% max | Increase instance or add pgbouncer | < 50% max |
| Redis memory > 70% | Increase node type | < 50% memory |

---

## Troubleshooting

### API Not Responding

```bash
# Check service status
docker compose ps api
kubectl -n driftwatch get pods -l app.kubernetes.io/name=driftwatch-api

# Check logs
docker compose logs --tail=100 api
kubectl -n driftwatch logs -l app.kubernetes.io/name=driftwatch-api --tail=100

# Check health endpoint
curl -v http://localhost:8000/api/health

# Common causes:
# - Database connection exhausted -> restart api, check DB connections
# - OOM killed -> increase memory limits
# - Migration not run -> run alembic upgrade head
```

### Workers Not Processing Tasks

```bash
# Check worker status
docker compose logs --tail=50 worker
celery -A worker.runner.celery_app inspect active

# Check Redis connectivity
docker compose exec redis redis-cli ping

# Check queue depth
celery -A worker.runner.celery_app inspect reserved

# Common causes:
# - Redis down -> restart Redis
# - Worker OOM -> increase memory limits, reduce concurrency
# - Task stuck -> inspect active tasks, revoke if needed
```

### Database Connection Issues

```bash
# Test connectivity
docker compose exec api python -c "from sqlalchemy import create_engine; e = create_engine('$DATABASE_URL'); e.connect()"

# Check active connections
docker compose exec db psql -U driftwatch -c "SELECT count(*) FROM pg_stat_activity;"

# Common causes:
# - Too many connections -> configure pgbouncer or increase max_connections
# - Slow queries -> check pg_stat_statements, add indexes
# - Disk full -> expand volume, clean old data
```

### Frontend Not Loading

```bash
# Check the current Vercel deployment and inspect build logs in the dashboard.

# Check API proxy
curl -v https://driftwatch.vercel.app/api/health

# Common causes:
# - Vercel build failed -> redeploy after fixing the frontend build
# - Rewrite misconfigured -> verify frontend/vercel.json and VITE_API_URL=/api
# - CORS issue -> verify CORS_ORIGINS env variable
```

### Drift Detection False Positives

- **Insufficient sample size**: Ensure at least 30 test cases per suite for statistical significance
- **High variance metrics**: Increase `drift_sensitivity` threshold in suite config
- **Transient LLM issues**: Configure retry policies and exclude outlier runs

---

## Incident Response

### Severity Levels

| Level | Description | Response Time | Example |
|-------|-------------|---------------|---------|
| P1 | Service down, data loss risk | 15 minutes | API unreachable, DB corruption |
| P2 | Degraded service | 1 hour | High latency, worker backlog |
| P3 | Minor issue | 4 hours | Dashboard cosmetic bug |
| P4 | Enhancement request | Next sprint | Feature request |

### Incident Workflow

1. **Detect** — Alert fires via Prometheus, hosting-provider alerts, or user report
2. **Acknowledge** — On-call engineer acknowledges within response SLA
3. **Triage** — Determine severity, affected components, blast radius
4. **Mitigate** — Apply immediate fix (rollback, scale up, failover)
5. **Resolve** — Deploy permanent fix
6. **Post-mortem** — Document timeline, root cause, action items within 48 hours

### Rollback Procedure

```bash
# Revert the deployment commit and push to main so Vercel + Render redeploy.
git revert <commit-sha>
git push origin main

# Only run a downgrade if the migration has a verified rollback path.
cd backend
alembic downgrade -1
```

Prefer a forward fix when a migration is already live and the downgrade path is uncertain. Production migrations should remain backward-compatible for one deploy cycle.

---

## SLO Definitions

### API Availability

- **Target**: 99.9% uptime (measured monthly)
- **Measurement**: Percentage of successful health checks (non-5xx)
- **Error budget**: 43.2 minutes of downtime per month

### API Latency

- **Target**: P99 latency < 500ms for non-evaluation endpoints
- **Measurement**: Prometheus histogram `driftwatch_http_request_duration_seconds`
- **Exclusions**: `POST /api/suites/{suite_id}/run` (long-running), file uploads

### Evaluation Throughput

- **Target**: 95% of evaluation runs complete within 2x expected duration
- **Measurement**: `driftwatch_evaluation_duration_seconds` vs configured timeout

### Error Budget Calculation

```
Error budget remaining = SLO target - actual error rate

Example (monthly):
  Total minutes: 43,200 (30 days)
  SLO target: 99.9%
  Allowed downtime: 43.2 minutes
  Actual downtime: 12 minutes
  Budget remaining: 31.2 minutes (72.2% remaining)
```

When error budget is exhausted:

- Freeze non-critical deployments
- Prioritize reliability work over features
- Require additional review for all changes

---

## Maintenance Windows

### Scheduled Maintenance

- **Window**: Sundays 03:00-05:00 UTC
- **Notification**: 48 hours advance notice via status page and Slack
- **Activities**: Database upgrades, infrastructure changes, certificate rotation

### Database Maintenance

```bash
# Run VACUUM and ANALYZE
docker compose exec db psql -U driftwatch -d driftwatch -c "VACUUM ANALYZE;"

# Reindex large tables
docker compose exec db psql -U driftwatch -d driftwatch -c "REINDEX TABLE evaluation_runs;"
```

### Certificate Rotation

- TLS certificates managed by cert-manager (Kubernetes) or ACM (AWS)
- Rotation: automatic before expiry
- API keys: rotate every 90 days, notify users 14 days before expiry

### Upgrade Procedures

**Python dependency updates:**

```bash
cd backend
pip-compile --upgrade requirements.in -o requirements.txt
# Test locally, then commit and deploy
```

**Node.js dependency updates:**

```bash
cd frontend
npm update
npm audit fix
npm run build  # verify build succeeds
```

**PostgreSQL major version upgrade:**

1. Create RDS snapshot
2. Test migration on staging
3. Schedule maintenance window
4. Apply Terraform change for engine version
5. Run `alembic upgrade head` post-migration
6. Verify application functionality
