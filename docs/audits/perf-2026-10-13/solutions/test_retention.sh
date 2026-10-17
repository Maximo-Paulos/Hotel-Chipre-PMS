#!/usr/bin/env bash
# Prueba la función de retención contra una base DESCARTABLE ya migrada con Alembic.
# Uso: DATABASE_URL_PSQL=postgresql://USER:PASS@127.0.0.1:5440/hotel_measure ./test_retention.sh
set -euo pipefail
P="psql $DATABASE_URL_PSQL -v ON_ERROR_STOP=1 -qAt"
HERE="$(cd "$(dirname "$0")" && pwd)"
$P -f "$HERE/retention_pg_cron.sql" >/dev/null
$P <<'SQL'
DELETE FROM rate_limit_events WHERE scope = 'retention_test';
DELETE FROM security_tokens WHERE token_type = 'retention_test';
INSERT INTO rate_limit_events(scope, subject_key, created_at) VALUES
  ('retention_test','old', now() - interval '3 days'), ('retention_test','new', now());
INSERT INTO security_tokens(token_type, subject_key, code_hash, expires_at, consumed_at) VALUES
  ('retention_test','expired','x', now() - interval '3 days', NULL),
  ('retention_test','consumed_old','x', now() + interval '1 day', now() - interval '3 days'),
  ('retention_test','live','x', now() + interval '1 day', NULL);
SELECT hotel_chipre_private.purge_operational_data();
SELECT 'rate_limit_events restantes: ' || count(*) FROM rate_limit_events WHERE scope='retention_test';
SELECT 'security_tokens restantes: ' || count(*) || ' (esperado 1: el vigente)' FROM security_tokens WHERE token_type='retention_test';
DELETE FROM rate_limit_events WHERE scope = 'retention_test';
DELETE FROM security_tokens WHERE token_type = 'retention_test';
SQL
