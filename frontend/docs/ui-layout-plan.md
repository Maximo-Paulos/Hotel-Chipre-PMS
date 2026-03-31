# Hotel Chipre PMS – UI Layout Plan

## Layout
- **Topbar:** slim stripe with product name, active hotel switcher, and user badge; sticks to top on scroll.
- **Sidebar (left, 280px):** navigation buckets: Operación (Dashboard, Reservas, Habitaciones), Proceso (Onboarding), Configuración (Usuarios, Hotel, Seguridad). Collapses to icons on small widths; mobile uses slide-in.
- **Content area:** max width 1280px, padded, uses cards for summary blocks and simple tables for lists. Background `slate-50`, cards `white` with subtle borders.

## Routing
- `/dashboard` (default) → overview cards + activity snippets.
- `/reservas` → tabla de reservas con estados y check-in/out.
- `/habitaciones` → inventario de habitaciones con estado de ocupación.
- `/onboarding/*` → wizard existente.
- `/settings/users`, `/settings/hotel`, `/settings/security` → ajustes.

## Data Model (mocked)
- `stats`: ocupación, ADR, revenue, próximas llegadas/salidas.
- `reservations`: id, huésped, habitación, fechas, estado, canal.
- `rooms`: número, categoría, piso, estado, notas rápidas.
- `activities`: breve feed para dashboard.

## Visual Prioridades
- Resaltar hotel activo y rol en topbar.
- Estado de conexión/onboarding en alert banner sobre contenido.
- Acciones rápidas en páginas (crear reserva, agregar habitación) como botones fantasma por ahora.

## Pending (future)
- Reemplazar mocks por API.
- Añadir filtros/búsqueda en reservas y habitaciones.
- Widgets de performance comparativos por fecha.
