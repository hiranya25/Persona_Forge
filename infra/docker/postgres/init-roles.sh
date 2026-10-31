#!/usr/bin/env bash
# Creates the two database roles Persona Forge uses and the application database.
#   pf_owner - owns the schema; used only to run migrations
#   pf_app   - used by the services; no ownership, so Row-Level Security applies
# Runs automatically in the Postgres container (docker-entrypoint-initdb.d) and can
# be run by hand against any Postgres as a superuser.
set -euo pipefail

: "${PF_DB_NAME:=personaforge}"
: "${PF_OWNER_PASSWORD:=pf_owner}"
: "${PF_APP_PASSWORD:=pf_app}"

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" --dbname postgres \
  -v db="$PF_DB_NAME" -v owner_pw="$PF_OWNER_PASSWORD" -v app_pw="$PF_APP_PASSWORD" <<'SQL'
SELECT format('CREATE ROLE pf_owner LOGIN PASSWORD %L', :'owner_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_owner') \gexec
SELECT format('CREATE ROLE pf_app LOGIN NOBYPASSRLS PASSWORD %L', :'app_pw')
WHERE NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'pf_app') \gexec
SELECT format('CREATE DATABASE %I OWNER pf_owner', :'db')
WHERE NOT EXISTS (SELECT 1 FROM pg_database WHERE datname = :'db') \gexec
SQL

psql -v ON_ERROR_STOP=1 --username "${POSTGRES_USER:-postgres}" --dbname "$PF_DB_NAME" <<'SQL'
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT ALL ON SCHEMA public TO pf_owner;
SQL
