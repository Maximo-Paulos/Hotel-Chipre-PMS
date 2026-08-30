---
name: new-permission
description: Add a granular permission for a specific action or view in Hotel Chipre PMS (e.g. "mover una reserva de habitación", "ver tarifas sin editarlas"), wire it through catalog, backend guard, frontend gate and migration, then verify it in a real browser with the affected roles. Use when the user asks for a new permission, a finer split between viewing and doing, or "que tal rol pueda X pero no Y".
---

# new-permission — agregar un permiso y probarlo de verdad

El catálogo separa lectura de acción a propósito: ver una sección nunca implica poder
modificarla. Un permiso nuevo tiene que atravesar **cinco capas** o queda decorativo.

Ejemplo canónico ya implementado: `reservation:move` protege mover una reserva de
habitación (`POST /api/reservations/{id}/room-move`, `app/api/reservations.py:985`), y es
distinto de `reservation:update`. Copiá ese patrón.

## Las cinco capas

Si salteás una, el permiso miente. Los dos bugs que encontramos auditando fueron
exactamente eso: `laundry:price_manage` existía en el catálogo y **ningún endpoint lo
usaba** (la casilla no hacía nada), y los permisos de vista sólo filtraban el menú
mientras la API seguía sirviendo los datos.

1. **Catálogo** — `app/services/permission_service.py`, `_CANONICAL_DEFINITIONS`:
   `code -> (module, description_en, help_es)`. El `help_es` son 1-3 frases que explican
   qué habilita **y qué no** — sale en el botón `i` de la pantalla. Es la única fuente:
   el frontend no duplica textos.
2. **Defaults** — `DEFAULT_MATRIX`. Regla dura: **nadie gana ni pierde acceso el día que
   se aplica**. Derivá el default de quién llega hoy a esa superficie, contando el guard
   de backend, no sólo la ruta del frontend. Ojo: una API suele alcanzarse por más roles
   que la ruta, porque la protege un permiso más amplio.
3. **Guard de backend** — `require_permission(...)` como dependencia, o
   `require_all_permissions(existente, nuevo)` si sumás una reja sobre un guard que ya
   existe. **Sumar, nunca reemplazar**: reemplazar ensancha el acceso.
4. **Gate de frontend** — `frontend/src/router.tsx` con `anyPermission={[...]}` y el item
   de `frontend/src/ui/AppShell.tsx` con `requiresAnyPermission`. No uses `roles={...}`:
   `PermissionGate` combina rol y permiso con **AND**, así que un `roles` puesto anula
   cualquier override que haga el dueño.
5. **Migración** — aditiva e idempotente; siembra el permiso y sus defaults sin pisar
   ninguna fila de `hotel_permission_overrides` (un operador puede haberla puesto a mano).

## Invariantes que no se tocan

- `_OWNER_ONLY` (`permissions:manage`, `hotel_settings:property_manage`,
  `hotel_settings:security_manage`, `apikey:manage`): el owner siempre los tiene y nadie
  más puede recibirlos. Es lo que impide que el dueño se autobloquee y pierda el hotel.
  Verificado: apagando 60 de 64 permisos, el owner conserva Permisos y API Keys.
- No hay ceilings por rol. El dueño puede dar o sacar cualquier otro permiso a cualquier rol.
- `hideForPreviewRoles` en `AppShell.tsx` es **sólo** para la vista previa de rol. Nunca
  lo uses para restringir al usuario real: escondería un link que la persona sí puede usar.

## Verificación en navegador (obligatoria)

Un permiso no está probado hasta que lo apagaste y viste que bloquea. Los tests no
alcanzan: los bugs 3 y 4 de la auditoría sólo aparecieron clickeando la pantalla.

### Levantar el entorno

```sh
cd "$(git rev-parse --show-toplevel)"
APP_ENV=test DATABASE_URL="sqlite:///$(pwd)/_e2e.db" .venv/bin/python scripts/seed_e2e_backend.py
APP_ENV=test DATABASE_URL="sqlite:///$(pwd)/_e2e.db" \
  .venv/bin/python -m uvicorn app.main:app --host 127.0.0.1 --port 8040 &
export PATH="$HOME/.local/node/bin:$PATH"; cd frontend && npm run dev &
```

`frontend/.env.local` (gitignored) debe tener `VITE_PUBLIC_APP_HOSTNAME=localhost` y
`VITE_API_URL=http://127.0.0.1:8040/api`, o el router manda al sitio de marketing.

Usuarios sembrados: `owner@e2e.com`/`E2ePass1234!`, `manager@e2e.com`/`E2eManager1234!`,
`receptionist@e2e.com`/`E2eReception1234!`, `housekeeping@e2e.com`/`E2eHousekeeping1234!`.
El co-owner hay que crearlo a mano; el seed no lo trae.

### El ciclo, por cada rol afectado

1. Entrá como owner, abrí `/settings/permissions`.
2. Clickeá la casilla del permiso en la columna de ese rol. Confirmá que la celda pase a
   **"Override de rol"** con link "Restaurar" — si no, no persistió.
3. Salí, entrá como ese rol.
4. Comprobá **las dos cosas**: que el link desaparezca del menú **y** que entrar por URL
   directa rebote. Ocultar el link no es un control de acceso.
5. Ejercitá la acción concreta (mover la reserva de habitación, guardar la tarifa) y
   confirmá que el backend responde 403.
6. Restaurá con "Restaurar defaults" de esa columna y verificá que vuelva al conteo original.

### Trampas del navegador

- Los inputs son controlados por React: asignar `.value` no actualiza el estado. Usá el
  setter nativo (`Object.getOwnPropertyDescriptor(HTMLInputElement.prototype,'value').set`)
  y disparar `input` con `bubbles:true`.
- La matriz tiene ~384 casillas: más de ~8 clicks por llamada cuelga el panel a los 45 s.
  Hacelo en tandas y consultá el conteo entre una y otra.
- Una sola cookie por origen: dos pestañas **no** sostienen dos sesiones distintas. Para
  probar dos roles, alterná logout/login en la misma pestaña.
- Si re-sembrás la base, **reiniciá el backend**: queda apuntando al archivo anterior y
  todo responde "Sesión revocada" con tokens recién emitidos.

## Gate antes de cerrar

```sh
.venv/bin/python -m pytest -q          # el set que falla debe seguir siendo el conocido
.venv/bin/python -m alembic heads      # un solo head
cd frontend && npm run lint && npm run typecheck && npm run build
npx playwright test role-journey --project=chromium   # 15/15
```

`role-journey.spec.ts` fija el contrato por rol. Si rompe, cambiaste acceso real — es un
bug de tu mapeo, no un test viejo. Sólo tocalo si el cambio de comportamiento es
deliberado, y decilo explícitamente.

**Nota sobre el baseline:** `pytest` desde la raíz falla 13 tests por una fuga del `.env`
local (`app/config.py` resuelve `env_file` contra el CWD). No son tuyos y no se arreglan
acá — compará contra ese set, no contra cero.

## Auditar todo el catálogo

Para barrer permiso × rol × endpoint automáticamente hay scripts de referencia en la
sesión de auditoría: extraen los guards con AST desde `app/api/*.py`, prenden y apagan
cada permiso con un login real por rol, y clasifican en `ok` / `fuga` /
`bloqueado_por_otro_guard`. Esa tercera categoría importa: un endpoint que da 403 **con
el permiso prendido** no prueba nada, y contarlo como éxito infla la cobertura.
