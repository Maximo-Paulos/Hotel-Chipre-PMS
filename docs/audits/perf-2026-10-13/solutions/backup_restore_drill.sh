#!/usr/bin/env bash
# S20: copia de seguridad lógica + restauración PROBADA (O7). Sirve para un piloto sin PITR.
#
#   SRC_URL     base a respaldar         (p. ej. la URL de sesión/directa de Supabase; NO el pooler 6543)
#   DRILL_URL   base ADMIN donde restaurar un esquema/base descartable (otra base, nunca la de producción)
#   OUT_DIR     carpeta del volcado (por defecto ./backups)
#   AGE_RECIPIENT  (opcional) clave pública de `age` para cifrar el volcado antes de subirlo
#
# Qué hace: pg_dump -Fc -> (cifra con age si se pide) -> restaura en una base nueva -> compara
# el conteo de filas de TODAS las tablas del esquema public -> borra la base de prueba.
# Sale con código != 0 si la restauración no reproduce los conteos (es el "drill").
set -euo pipefail
: "${SRC_URL:?falta SRC_URL}"; : "${DRILL_URL:?falta DRILL_URL}"
OUT_DIR="${OUT_DIR:-./backups}"; mkdir -p "$OUT_DIR"
STAMP="$(date -u +%Y%m%dT%H%M%SZ)"
DUMP="$OUT_DIR/hotel-$STAMP.dump"
DRILL_DB="restore_drill_$STAMP"

echo "[1/5] pg_dump -> $DUMP"
pg_dump --format=custom --no-owner --no-privileges --file="$DUMP" "$SRC_URL"
ls -l "$DUMP" | awk '{print "      tamaño:", $5, "bytes"}'

echo "[2/5] crea la base de prueba $DRILL_DB"
psql "$DRILL_URL" -v ON_ERROR_STOP=1 -qc "CREATE DATABASE \"$DRILL_DB\""
DRILL_DB_URL="$(python3 - "$DRILL_URL" "$DRILL_DB" <<'PY'
import sys, urllib.parse as u
p = u.urlsplit(sys.argv[1]); print(u.urlunsplit(p._replace(path="/" + sys.argv[2])))
PY
)"
cleanup() { psql "$DRILL_URL" -qc "DROP DATABASE IF EXISTS \"$DRILL_DB\" WITH (FORCE)" >/dev/null 2>&1 || true; }
trap cleanup EXIT

echo "[3/5] pg_restore en $DRILL_DB"
pg_restore --no-owner --no-privileges --exit-on-error --dbname="$DRILL_DB_URL" "$DUMP"

echo "[4/5] compara conteos de filas (public)"
COUNTS_SQL="SELECT format('%I', table_name) FROM information_schema.tables WHERE table_schema='public' AND table_type='BASE TABLE' ORDER BY 1"
bad=0; n=0
while IFS= read -r t; do
  a="$(psql "$SRC_URL" -Atc "SELECT count(*) FROM public.$t")"
  b="$(psql "$DRILL_DB_URL" -Atc "SELECT count(*) FROM public.$t")"
  n=$((n+1))
  if [ "$a" != "$b" ]; then echo "      DIFIERE $t: origen=$a restaurado=$b"; bad=$((bad+1)); fi
done < <(psql "$SRC_URL" -Atc "$COUNTS_SQL")
echo "      tablas comparadas: $n, con diferencias: $bad"

if [ -n "${AGE_RECIPIENT:-}" ]; then
  echo "[5/5] cifra con age -> $DUMP.age (borra el volcado en claro)"
  age -r "$AGE_RECIPIENT" -o "$DUMP.age" "$DUMP" && rm -f "$DUMP"
else
  echo "[5/5] sin AGE_RECIPIENT: el volcado queda EN CLARO; cífrelo antes de subirlo a un bucket"
fi
[ "$bad" = 0 ] && [ "$n" -gt 0 ] && echo "DRILL OK" || { echo "DRILL FALLO"; exit 1; }
