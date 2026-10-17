#!/usr/bin/env bash
# Prueba de S19 contra un PostgreSQL descartable (NO usar contra producción).
# Uso: PGHOST=127.0.0.1 PGPORT=5440 PGUSER=pgtest PGPASSWORD=pgtest bash test_api_key_lookup.sh [base]
# Requiere una base con la tabla hotel_api_keys (RLS FORCE) y un rol NOBYPASSRLS "app_rls_probe".
set -euo pipefail
DB="${1:-hotel_measure}"
HERE="$(cd "$(dirname "$0")" && pwd)"
admin() { psql -v ON_ERROR_STOP=1 -At -d "$DB" "$@"; }
probe() { PGPASSWORD=probe psql -v ON_ERROR_STOP=1 -At -U app_rls_probe -d "$DB" "$@"; }

admin -c "DO \$\$ BEGIN IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname='app_rls_probe') THEN
  CREATE ROLE app_rls_probe LOGIN PASSWORD 'probe' NOSUPERUSER NOBYPASSRLS; END IF; END \$\$;" >/dev/null
admin -c "GRANT SELECT, UPDATE ON hotel_api_keys TO app_rls_probe" >/dev/null
admin -f "$HERE/api_key_lookup_under_rls.sql" >/dev/null
admin -c "GRANT USAGE ON SCHEMA hotel_chipre_private TO app_rls_probe;
          GRANT EXECUTE ON FUNCTION hotel_chipre_private.lookup_api_key(text) TO app_rls_probe" >/dev/null

HASH="$(admin -c "SELECT key_hash FROM hotel_api_keys ORDER BY id LIMIT 1")"
[ -n "$HASH" ] || { echo "FALLO: no hay ninguna clave de prueba en hotel_api_keys"; exit 2; }

before="$(probe -c "SELECT count(*) FROM hotel_api_keys WHERE key_hash = '$HASH'")"
after="$(probe -c "SELECT count(*) FROM hotel_chipre_private.lookup_api_key('$HASH')")"
none="$(probe -c "SELECT count(*) FROM hotel_chipre_private.lookup_api_key('no-existe')")"
other="$(probe -c "SELECT count(*) FROM hotel_api_keys")"   # sin app.hotel_id no debe ver filas

echo "consulta directa sin contexto (hoy):        $before  (esperado 0: es el bug)"
echo "lookup_api_key(hash) sin contexto (S19):    $after  (esperado 1)"
echo "lookup_api_key('no-existe'):                $none  (esperado 0)"
echo "SELECT * sin contexto sigue aislado:        $other  (esperado 0)"
[ "$before" = 0 ] && [ "$after" = 1 ] && [ "$none" = 0 ] && [ "$other" = 0 ] && echo "OK" || { echo "FALLO"; exit 1; }
