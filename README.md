# eligibility-group

**Payer / employer / subgroup hierarchy + plan visibility**.

## What this service does

Hierarchy: a payer (e.g. ICICI) contracts with employers (Swiggy, Zomato) which split into subgroups. The `employer_plan_visibility` table controls which plans each employer can offer to its members.

Powers the **Groups admin UI** (bonus assignment task) — full CRUD: create/delete payers, employers (with cascade), subgroups, attach/detach plan visibility per employer.

This is **one of 7 microservices** in the [Eligibility & Enrollment Platform](https://github.com/SamieZian/eligibility-platform). Each service has its own repo, its own database, its own Dockerfile, its own deployment lifecycle.

## Prerequisites

| Tool | Version | Why |
|---|---|---|
| Docker | 24+ | Container runtime |
| Docker Compose | v2 (the `docker compose` plugin) | Local orchestration |
| Python | 3.11+ | Standalone dev (optional) |
| GNU Make | any recent | Convenience targets (optional) |

The easiest way to use this service is via the orchestration repo:
```bash
git clone https://github.com/SamieZian/eligibility-platform
cd eligibility-platform
./bootstrap.sh         # clones this repo and 6 siblings
make up                # boots the whole stack with this svc included
```

## Companion repos

| Repo | What |
|---|---|
| [`eligibility-platform`](https://github.com/SamieZian/eligibility-platform) | Orchestration + docker-compose + sample 834 + demo |
| [`eligibility-atlas`](https://github.com/SamieZian/eligibility-atlas) | Bitemporal enrollment service |
| [`eligibility-member`](https://github.com/SamieZian/eligibility-member) | Members + dependents (KMS-encrypted SSN) |
| [`eligibility-group`](https://github.com/SamieZian/eligibility-group) | Payer / employer / subgroup / plan visibility |
| [`eligibility-plan`](https://github.com/SamieZian/eligibility-plan) | Plan catalog (Redis cache-aside) |
| [`eligibility-bff`](https://github.com/SamieZian/eligibility-bff) | GraphQL gateway + file upload |
| [`eligibility-workers`](https://github.com/SamieZian/eligibility-workers) | Stateless workers — ingestion / projector / outbox-relay |
| [`eligibility-frontend`](https://github.com/SamieZian/eligibility-frontend) | React + TS UI |

## Quickstart (standalone, with this repo only)

```bash
# 1. Configure
cp .env.example .env
# (edit values if needed — defaults work for local docker)

# 2. Build the image
docker build -t eligibility-group:local .

# 3. Spin a Postgres for it
docker run -d --name pg-group \
  -e POSTGRES_PASSWORD=dev_pw \
  -p 5443:5432 postgres:15-alpine

# 4. Run the service against that DB
docker run --rm -p 6443:8000 \
  --env-file .env \
  -e DATABASE_URL=postgresql+psycopg://postgres:dev_pw@host.docker.internal:5443/postgres \
  eligibility-group:local

# 5. Health check
curl http://localhost:6443/livez
```

## Develop locally without Docker

```bash
# Prereqs: Python 3.11+, Poetry 1.8+
poetry install
poetry run python -m app.main
poetry run pytest tests -q
```

## Project layout (hexagonal)

```
.
├── app/
│   ├── domain/         # Pure business logic — no I/O
│   ├── application/    # Use-cases, command handlers
│   ├── infra/          # SQLAlchemy repos, KMS, Redis, ORM models
│   ├── interfaces/     # FastAPI routers (HTTP)
│   ├── settings.py     # Pydantic env-driven config
│   └── main.py         # FastAPI app + lifespan
├── tests/              # pytest unit tests
├── migrations/         # Alembic (prod schema migrations)
├── libs/               # Vendored shared code
│   └── python-common/  # outbox, pubsub, errors, retry, circuit breaker, kms
├── .env.example        # All env vars documented
├── Dockerfile
├── pyproject.toml
└── README.md
```

## Environment variables

See [`.env.example`](.env.example) for the full list with defaults. Required:

- `SERVICE_NAME` — used in logs/traces
- `DATABASE_URL` — Postgres connection string
- `PUBSUB_PROJECT_ID` — Pub/Sub project (any value for local emulator)
- `PUBSUB_EMULATOR_HOST` — `pubsub:8085` when running with compose, unset in prod

Optional:
- `LOG_LEVEL` (`INFO`)
- `OTEL_EXPORTER_OTLP_ENDPOINT` — when set, traces export to that endpoint
- `TENANT_DEFAULT` — fallback tenant id when no header

## API

See `app/interfaces/api.py` for the route list. Standard endpoints:

- `GET /livez` → liveness probe
- `GET /readyz` → readiness probe (checks deps reachable)

## Testing via curl

Service listens on port **8003**.

```bash
BASE=http://localhost:8003
T=11111111-1111-1111-1111-111111111111
H=(-H "Content-Type: application/json" -H "X-Tenant-Id: $T")
```

**Payers**

```bash
# Create
PAYER=$(curl -s -X POST $BASE/payers "${H[@]}" \
  -d '{"name": "United Healthcare"}' | jq -r .id)

# List
curl -s $BASE/payers -H "X-Tenant-Id: $T" | jq .
```

**Employers**

```bash
# Create under a payer
EMP=$(curl -s -X POST $BASE/employers "${H[@]}" \
  -d "{\"payer_id\": \"$PAYER\", \"name\": \"Swiggy\", \"external_id\": \"SWIGGY\"}" \
  | jq -r .id)

# List / find by external_id (used by 834 ingestion to resolve REF*38)
curl -s "$BASE/employers" -H "X-Tenant-Id: $T" | jq .
curl -s "$BASE/employers?external_id=SWIGGY" -H "X-Tenant-Id: $T" | jq .

# Delete
curl -s -X DELETE "$BASE/employers/$EMP" -H "X-Tenant-Id: $T"
```

**Subgroups** (nested under employer)

```bash
SUB=$(curl -s -X POST $BASE/subgroups "${H[@]}" \
  -d "{\"employer_id\": \"$EMP\", \"name\": \"SWIGGY-A\"}" | jq -r .id)

curl -s "$BASE/employers/$EMP/subgroups" -H "X-Tenant-Id: $T" | jq .

curl -s -X DELETE "$BASE/subgroups/$SUB" -H "X-Tenant-Id: $T"
```

**Plan visibility** (which employer can offer which plan)

```bash
PLAN=33333333-3333-3333-3333-333333333333

# Attach
curl -s -X POST $BASE/visibility "${H[@]}" \
  -d "{\"employer_id\": \"$EMP\", \"plan_id\": \"$PLAN\"}" | jq .

# List plans visible to an employer
curl -s "$BASE/employers/$EMP/plans" -H "X-Tenant-Id: $T" | jq .
```

## Patterns used

- Hexagonal architecture (domain / application / infra / interfaces)
- SQLAlchemy 2.0 ORM with `pg_insert.on_conflict_do_update` for idempotent upserts
- Transactional outbox for at-least-once event delivery
- Structured JSON logs with correlation ID propagation
- OpenTelemetry traces (BFF → service → DB)
- Circuit breakers on outbound HTTP

## License

MIT.
