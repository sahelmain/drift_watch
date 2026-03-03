# DriftWatch Architecture

## System Overview

DriftWatch is a platform for continuous LLM evaluation and drift monitoring. It combines a Python CLI/SDK, a FastAPI backend with Celery workers, a React dashboard, and a PostgreSQL + Redis data layer.

```mermaid
graph TB
    subgraph Clients["Client Layer"]
        CLI["CLI / SDK<br/>Python package"]
        Dashboard["Dashboard<br/>React + TypeScript"]
    end

    subgraph API_Layer["API Layer"]
        API["FastAPI<br/>REST API"]
        Auth["Auth Middleware<br/>JWT + API Keys"]
    end

    subgraph Worker_Layer["Worker Layer"]
        Workers["Celery Workers<br/>Evaluation execution"]
        Scheduler["Beat Scheduler<br/>Cron-based triggers"]
        DriftEngine["Drift Engine<br/>Statistical analysis"]
    end

    subgraph Data_Layer["Data Layer"]
        DB[("PostgreSQL 16<br/>Primary datastore")]
        Redis[("Redis 7<br/>Broker + cache")]
    end

    subgraph Observability["Observability"]
        Prom["Prometheus"]
        Grafana["Grafana"]
        Logs["CloudWatch Logs"]
    end

    subgraph External["External Services"]
        OpenAI["OpenAI API"]
        Anthropic["Anthropic API"]
        Google["Google AI"]
        Slack["Slack"]
        PagerDuty["PagerDuty"]
    end

    CLI -->|HTTPS| API
    Dashboard -->|HTTPS| API
    API --> Auth
    Auth --> API
    API --> DB
    API --> Redis
    Scheduler -->|Enqueue| Redis
    Redis -->|Dequeue| Workers
    Workers --> DriftEngine
    Workers --> DB
    Workers --> OpenAI
    Workers --> Anthropic
    Workers --> Google
    Workers --> Slack
    Workers --> PagerDuty
    API -.->|/metrics| Prom
    Prom --> Grafana
    API -.-> Logs
    Workers -.-> Logs
```

## Component Descriptions

### CLI / SDK (`driftwatch/`)

The Python package published to PyPI. Provides:

- **CLI** (`driftwatch run`, `driftwatch suites list`, etc.) for terminal-based workflows
- **Python client** (`driftwatch.Client`) for programmatic access
- **Configuration parser** for YAML test suite definitions
- Communicates with the backend over HTTP

### FastAPI API (`backend/app/`)

The central REST API handling all client requests:

- **Authentication** via JWT tokens (dashboard) and API keys (CLI/SDK)
- **Evaluation management** — CRUD operations on test suites and evaluation runs
- **Drift analysis** — query drift reports and threshold violations
- **Prometheus metrics** endpoint at `/api/metrics`
- **WebSocket** support for live evaluation progress

### Celery Workers (`backend/worker/`)

Background task processors responsible for:

- Executing evaluation test cases against LLM providers
- Running drift detection algorithms (KS-test, Mann-Whitney U, custom)
- Sending alert notifications when thresholds are breached
- Processing scheduled evaluation batches

### Beat Scheduler

Celery Beat process that triggers evaluations based on cron schedules defined in test suites.

### React Dashboard (`frontend/`)

Single-page application built with React 18, TypeScript, and Vite:

- Real-time evaluation monitoring
- Historical metric visualization (charts, heatmaps)
- Test suite management interface
- Drift detection alerts and timeline
- Configuration and settings management

### PostgreSQL Database

Primary datastore holding:

- Test suite definitions and configurations
- Evaluation run results and individual test case outcomes
- Metric time-series data
- User accounts and API keys
- Alert history

### Redis

Serves two roles:

- **Message broker** for Celery task queue
- **Cache layer** for API response caching and rate limiting

## Data Flow Diagrams

### Test Execution Flow

```mermaid
sequenceDiagram
    actor User
    participant CLI as CLI / Dashboard
    participant API as FastAPI
    participant Redis
    participant Worker as Celery Worker
    participant LLM as LLM Provider
    participant DB as PostgreSQL

    User->>CLI: driftwatch run --config suite.yml
    CLI->>API: POST /api/evaluations
    API->>DB: Create evaluation run record
    API->>Redis: Enqueue evaluation tasks
    API-->>CLI: 202 Accepted (run_id)

    loop For each test case
        Redis->>Worker: Dequeue task
        Worker->>LLM: Send prompt
        LLM-->>Worker: Response
        Worker->>Worker: Score metrics
        Worker->>DB: Store results
    end

    Worker->>DB: Finalize run (aggregate scores)
    CLI->>API: GET /api/evaluations/{run_id}
    API->>DB: Fetch results
    API-->>CLI: Evaluation results
```

### Drift Detection Flow

```mermaid
sequenceDiagram
    participant Scheduler as Beat Scheduler
    participant Redis
    participant Worker as Celery Worker
    participant DB as PostgreSQL
    participant Notify as Slack / PagerDuty

    Scheduler->>Redis: Trigger scheduled evaluation
    Redis->>Worker: Dequeue evaluation tasks
    Worker->>DB: Fetch baseline metrics
    Worker->>Worker: Execute test suite
    Worker->>Worker: Statistical comparison (KS-test)
    Worker->>DB: Store drift analysis

    alt Drift exceeds threshold
        Worker->>Notify: Send alert
        Worker->>DB: Record alert event
    end
```

### Alert Flow

```mermaid
sequenceDiagram
    participant Worker as Celery Worker
    participant DB as PostgreSQL
    participant Slack
    participant PD as PagerDuty
    participant WH as Webhooks

    Worker->>Worker: Detect threshold violation
    Worker->>DB: Create alert record

    par Notify all channels
        Worker->>Slack: Post drift alert
        Worker->>PD: Create incident
        Worker->>WH: POST to configured URLs
    end
```

## Database Schema Overview

```mermaid
erDiagram
    users {
        uuid id PK
        string email UK
        string hashed_password
        string role
        timestamp created_at
    }
    api_keys {
        uuid id PK
        uuid user_id FK
        string key_hash UK
        string name
        timestamp expires_at
    }
    test_suites {
        uuid id PK
        uuid user_id FK
        string name
        jsonb config
        string schedule
        timestamp created_at
    }
    evaluation_runs {
        uuid id PK
        uuid suite_id FK
        string status
        jsonb aggregate_metrics
        timestamp started_at
        timestamp completed_at
    }
    test_results {
        uuid id PK
        uuid run_id FK
        integer case_index
        jsonb input
        text output
        jsonb metrics
        float latency_ms
    }
    drift_reports {
        uuid id PK
        uuid suite_id FK
        uuid baseline_run_id FK
        uuid comparison_run_id FK
        jsonb drift_metrics
        boolean threshold_breached
        timestamp created_at
    }
    alerts {
        uuid id PK
        uuid drift_report_id FK
        string channel
        string status
        timestamp sent_at
    }

    users ||--o{ api_keys : "has"
    users ||--o{ test_suites : "owns"
    test_suites ||--o{ evaluation_runs : "produces"
    evaluation_runs ||--o{ test_results : "contains"
    test_suites ||--o{ drift_reports : "analyzed in"
    drift_reports ||--o{ alerts : "triggers"
```

## API Design Principles

- **RESTful** — resources are nouns, HTTP verbs for actions
- **Versioned** — all endpoints under `/api/` (future: `/api/v2/`)
- **Pagination** — cursor-based pagination for list endpoints
- **Consistent errors** — RFC 7807 problem detail format
- **Async** — all database I/O is async (SQLAlchemy + asyncpg)
- **Idempotent** — safe retries with idempotency keys for POST operations
- **Rate limited** — token bucket per API key, stored in Redis

## Security Architecture

### Authentication Flow

```mermaid
sequenceDiagram
    actor User
    participant Client
    participant API
    participant DB

    alt Dashboard Login
        User->>Client: Enter credentials
        Client->>API: POST /api/auth/login
        API->>DB: Verify credentials
        API-->>Client: JWT access + refresh tokens
        Client->>API: Requests with Authorization: Bearer <jwt>
    end

    alt SDK / CLI
        User->>Client: Configure API key
        Client->>API: Requests with X-API-Key header
        API->>DB: Verify key hash + permissions
    end
```

### Security Layers

- **Transport** — TLS everywhere (enforced at ingress/load balancer)
- **Authentication** — JWT (dashboard) + API keys (SDK/CI)
- **Authorization** — Role-based access control (admin, member, viewer)
- **Input validation** — Pydantic models for all request bodies
- **SQL injection** — parameterized queries via SQLAlchemy ORM
- **Rate limiting** — per-key limits stored in Redis
- **Secrets** — Kubernetes Secrets / AWS Secrets Manager, never in code

## Deployment Architecture

### Local Development (Docker Compose)

All services run locally via `docker compose up`. Suitable for development and small-scale self-hosting.

```mermaid
graph LR
    subgraph Docker Compose
        FE[Frontend :3000]
        API[API :8000]
        W[Workers]
        S[Scheduler]
        DB[(Postgres :5432)]
        R[(Redis :6379)]
        P[Prometheus :9090]
        G[Grafana :3001]
    end
    FE --> API
    API --> DB
    API --> R
    R --> W
    S --> R
    W --> DB
    API -.-> P
    P --> G
```

### AWS Production (Terraform)

EC2 instance running Docker Compose, backed by managed RDS and ElastiCache. CloudWatch for logging and alerting.

```mermaid
graph TB
    subgraph VPC
        subgraph Public Subnet
            EC2[EC2 t3.medium<br/>Docker Compose]
        end
        subgraph Private Subnet
            RDS[(RDS PostgreSQL<br/>db.t3.micro)]
            ElastiCache[(ElastiCache Redis<br/>cache.t3.micro)]
        end
    end
    S3[(S3 Backups)]
    CW[CloudWatch]

    EC2 --> RDS
    EC2 --> ElastiCache
    EC2 --> S3
    EC2 -.-> CW
```

### Kubernetes (Production-scale)

For larger deployments, Kubernetes manifests provide auto-scaling, rolling updates, and high availability.

```mermaid
graph TB
    subgraph K8s Cluster
        Ingress[Nginx Ingress]
        subgraph driftwatch namespace
            FE[Frontend Pods x2]
            API[API Pods 2-10<br/>HPA]
            W[Worker Pods x2]
        end
    end
    ExtDB[(External RDS)]
    ExtRedis[(External ElastiCache)]

    Ingress -->|/| FE
    Ingress -->|/api| API
    API --> ExtDB
    API --> ExtRedis
    W --> ExtDB
    W --> ExtRedis
```
