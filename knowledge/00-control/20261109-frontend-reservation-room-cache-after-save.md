---
kind: checkpoint
scope: project
status: inferred
agent: frontend-engineer
created_at: 2026-11-09T09:20:00Z
project: hotel-chipre-pms
code_sha: 1133dc35
---

# Caché de habitación después de guardar una reserva

## Hallazgo

La evidencia de QA cloud recibida en esta tarea mostró que la ficha y la lista de Owner podían conservar la habitación anterior después de guardar una reserva, aunque otra pestaña ya mostrara la habitación nueva. La recarga de Owner mostraba el dato correcto. En el código, tanto la coedición como la mutación normal iniciaban la revalidación en segundo plano sin aplicar primero la respuesta confirmada a las vistas abiertas.

## Cambio y evidencia

- `updateReservationCacheFromCommittedPatch` cancela lecturas anteriores del detalle exacto y las listas de reservas del hotel afectado, mezcla el resultado confirmado en las entradas existentes y vuelve a invalidar esas vistas para reconciliarse en segundo plano.
- `ReservationsPage.tsx` aplica el recurso guardado por coedición, resuelve `room_number` desde la consulta de habitaciones y actualiza también el guardado por el endpoint normal.
- La regresión cubre habitación nueva en ficha y listas, aislamiento por hotel y reserva, y una respuesta de lectura antigua en vuelo. Suite focal: 20/20; suite frontend: 187/187.
- `npm run lint`, `npm run typecheck` y `npm run build` pasaron sobre `main` integrado hasta `2d196e7d`.

## Validación y límites

- Commit de código: `1133dc3545cb6a0c7a37837bcf8c0065229f090b`.
- Cloud QA aportó el repro antes del cambio; falta repetirlo en el preview aislado después del despliegue de este código.
- Graphify update, build de flujos, normalización, portable-check y check-update pasaron localmente. El extractor AST reportó tres archivos Swift sin gramática disponible; los artefactos Graphify e inventarios se dejaron fuera del diff funcional.
