-- Retención de tablas que crecen sin tope (hallazgo N11 del informe).
-- Sigue el patrón de alembic/versions/20260925_public_inquiry_retention.py:
-- función en el esquema privado + trabajo de pg_cron. Se borra por lotes para no
-- sostener bloqueos largos. Probada en PostgreSQL 16 (sin pg_cron) con
-- solutions/test_retention.sh; el `cron.schedule` final requiere pg_cron
-- (Supabase lo trae) y NO se ejecutó aquí.
--
-- Requisitos: el rol que corre el trabajo debe saltear RLS (en Supabase, pg_cron corre
-- como `postgres`) porque `domain_event_outbox` tiene FORCE ROW LEVEL SECURITY.
-- Antes de activarlo, confirmar que `_replay_or_reset` (app/services/domain_events.py:1780)
-- emite un reinicio cuando el cursor pedido es anterior a la fila más antigua retenida.

CREATE SCHEMA IF NOT EXISTS hotel_chipre_private;

CREATE OR REPLACE FUNCTION hotel_chipre_private.purge_operational_data()
RETURNS void
LANGUAGE plpgsql
SET search_path = pg_catalog
AS $function$
DECLARE
    utc_now timestamp without time zone := pg_catalog.timezone('UTC', pg_catalog.clock_timestamp());
    now_tz  timestamptz := pg_catalog.clock_timestamp();
    batch   constant integer := 10000;
    n_rate bigint; n_tokens bigint; n_outbox bigint; n_dead bigint;
BEGIN
    -- Ventanas de límite de intentos: de minutos; se conserva 1 día de margen para auditoría.
    DELETE FROM public.rate_limit_events
    WHERE id IN (SELECT id FROM public.rate_limit_events
                 WHERE created_at < utc_now - INTERVAL '1 day' ORDER BY id LIMIT batch);
    GET DIAGNOSTICS n_rate = ROW_COUNT;

    -- Códigos de un solo uso: vencidos o consumidos hace más de 1 día.
    DELETE FROM public.security_tokens
    WHERE id IN (SELECT id FROM public.security_tokens
                 WHERE expires_at < utc_now - INTERVAL '1 day'
                    OR consumed_at < utc_now - INTERVAL '1 day' ORDER BY id LIMIT batch);
    GET DIAGNOSTICS n_tokens = ROW_COUNT;

    -- Outbox: eventos ya publicados con más de 7 días.
    DELETE FROM public.domain_event_outbox
    WHERE id IN (SELECT id FROM public.domain_event_outbox
                 WHERE published_at IS NOT NULL AND published_at < now_tz - INTERVAL '7 days'
                 ORDER BY id LIMIT batch);
    GET DIAGNOSTICS n_outbox = ROW_COUNT;

    -- Outbox: eventos en cola muerta ya resueltos, 30 días.
    DELETE FROM public.domain_event_outbox
    WHERE id IN (SELECT id FROM public.domain_event_outbox
                 WHERE resolved_at IS NOT NULL AND resolved_at < now_tz - INTERVAL '30 days'
                 ORDER BY id LIMIT batch);
    GET DIAGNOSTICS n_dead = ROW_COUNT;

    RAISE LOG 'operational retention rate_limit_events=% security_tokens=% outbox_published=% outbox_resolved=%',
        n_rate, n_tokens, n_outbox, n_dead;
END
$function$;

REVOKE ALL ON FUNCTION hotel_chipre_private.purge_operational_data() FROM PUBLIC;

-- Solo con pg_cron instalado (cada hora, minuto 17 para no coincidir con otros trabajos):
-- SELECT cron.schedule('hotel-chipre-operational-retention', '17 * * * *',
--                      'SELECT hotel_chipre_private.purge_operational_data()');
