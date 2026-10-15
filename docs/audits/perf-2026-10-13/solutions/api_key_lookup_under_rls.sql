-- S19: búsqueda de la clave de API pública compatible con RLS FORCE (M4).
--
-- Problema: hotel_api_keys tiene RLS FORCE con política
--   hotel_id = NULLIF(current_setting('app.hotel_id', true), '')::integer
-- pero verify_key() busca la fila por key_hash ANTES de saber el hotel.
-- Con un rol NOBYPASSRLS la consulta devuelve 0 filas => toda clave da 401.
--
-- Solución: una función SECURITY DEFINER cuya dueña sea un rol con BYPASSRLS (con FORCE,
-- ni el dueño de la tabla se salta la política; en Supabase el rol `postgres` lo tiene:
-- needs-verification) y que devuelve SOLO la fila de ese hash. La política de
-- la tabla no se toca: el resto de los accesos sigue aislado por hotel.
--
-- Probar:  bash solutions/test_api_key_lookup.sh
CREATE SCHEMA IF NOT EXISTS hotel_chipre_private;

CREATE OR REPLACE FUNCTION hotel_chipre_private.lookup_api_key(p_key_hash text)
RETURNS TABLE (
    id integer, hotel_id integer, key_prefix character varying, purpose text,
    is_active boolean, expires_at timestamp without time zone
)
LANGUAGE sql
STABLE
SECURITY DEFINER
SET search_path = pg_catalog, public
AS $$
    SELECT k.id, k.hotel_id, k.key_prefix, k.purpose::text, k.is_active, k.expires_at
    FROM public.hotel_api_keys k
    WHERE k.key_hash = p_key_hash
    LIMIT 1
$$;

REVOKE ALL ON FUNCTION hotel_chipre_private.lookup_api_key(text) FROM PUBLIC;
-- GRANT EXECUTE ... TO <rol de la aplicación>;   (el rol real de DATABASE_URL)

-- Índice que la búsqueda necesita (hoy no existe: M3).
CREATE UNIQUE INDEX IF NOT EXISTS ux_hotel_api_keys_key_hash ON public.hotel_api_keys (key_hash);
