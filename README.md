# Persona Forge

A multi-tenant platform for **rule-following AI assistants**. Companies get assistants that
answer only from approved documents, follow a versioned rule set (a *persona*), have every
answer checked by trained verifier models before anyone sees it, and record everything in a
tamper-evident audit log.

Everything runs on free tooling and a laptop CPU. The full design (architecture, AI pipeline,
data model, security, training plan, and roadmap) is in
**[docs/system-design.md](docs/system-design.md)**.

## Status

| Phase | Scope | State |
|---|---|---|
| **P0 — Foundations** | Monorepo, auth with MFA, companies/users/roles, Row-Level Security, hash-chained audit log, both portal shells, CI | ✅ Done |
| P1 — Documents & baseline RAG | Ingestion, hybrid search, writer LLM, chat with citations, eval harness | Next |
| P2–P5 | Guardrails, trained verifiers, writer tuning, production launch | Planned |

## Repository layout

```
apps/web/            React + TypeScript — Admin portal (/admin) and Company portal (/app)
services/api/        FastAPI modular monolith, Alembic migrations, tests
infra/docker/        Database role setup (and later: proxy, dashboards)
docs/                System design; legacy/ui-mock holds the original clickable mock
compose.yaml         Local development stack
```

## Quick start (Docker)

```bash
docker compose up --build
```

Then create the first Platform Admin:

```bash
docker compose exec api python -m app.cli create-platform-admin --email you@example.com --name "Your Name"
```

| URL | What |
|---|---|
| http://localhost:5173 | Web app: sign in, set up your second factor, create a company |
| http://localhost:8025 | Mailpit: every email the app sends (invitations, sign-in codes) |
| http://localhost:8000/api/docs | Interactive API documentation |

## How sign-in works

| Who | How |
|---|---|
| Platform Admin, Company Admin | Password, then a **mandatory** second factor (authenticator app or email code); 10 one-time recovery codes |
| Analyst, Reviewer, Viewer | Account created by their Company Admin; sign in with **password or an email code** |

Companies join by invitation only: the Platform Admin creates a company and invites its
Company Admin, who then creates the rest of the team.

## Development without Docker

Needs Python 3.12+, [uv](https://docs.astral.sh/uv/), Node 22, and Postgres 16.

```bash
# once: create the database roles (as a Postgres superuser)
PGHOST=localhost PGPASSWORD=postgres bash infra/docker/postgres/init-roles.sh

cd services/api
uv sync
cp .env.example .env          # set EMAIL_BACKEND=console to print emails to the log
uv run alembic upgrade head
uv run uvicorn app.main:app --reload

cd apps/web
npm install
npm run dev
```

## Tests

```bash
cd services/api && uv run pytest     # needs Postgres; see tests/conftest.py
cd apps/web && npm test
```

The API suite includes a **cross-tenant isolation suite** that checks every company boundary,
both through the API and with raw SQL against Postgres Row-Level Security, plus tamper tests
for the audit log.
