# SDD ledger — plan: /Users/maximopaulos/AI-Workspace/projects/TECH-0140-plan.md

## Preflight scan

### Shared interface and file pairs

| Tareas | Interfaz/archivo compartido | Resultado del chequeo |
|---|---|---|
| T0/T1 | config, `.env.example`, auth docs | T0 documenta baseline; T1 agrega flags sin secretos y no contradice auth existente. |
| T0/T3 | arquitectura híbrida, infraestructura | T0 fija PostgreSQL/Redis roles; T3 implementa puertos sin cambiar autoridad. |
| T0/T4 | outbox docs/model/migration inventory | T0 describe deuda; T4 la resuelve aditivamente sin downgrade destructivo. |
| T1/T5 | frontend session/auth/realtime | T1 entrega sesión segura; T5 usa esa sesión y no mezcla OAuth. |
| T2/T4 | `domain_event_outbox`, cursor | T2 usa `id` temporal; T4 mantiene compatibilidad y agrega `stream_cursor`. |
| T2/T5 | recovery/SSE contract | T2 devuelve sólo dominios/cursor; T5 consume sin payload de negocio. |
| T3/T4 | Redis/EventBus/publisher | T3 abstrae transporte; T4 conserva outbox durable si Redis falla. |
| T3/T8 | locks/dispatcher | T3 conserva advisory fallback; T8 usa lease idempotente. |
| T3/T9 | health/datastores | T3 expone fallos; T9 clasifica Redis como degradación opcional salvo lock crítico. |
| T4/T5 | `event_id`, cursor, replay | T4 hace durable el cursor; T5 deduplica y cubre gaps. |
| T4/T8 | tasks/Celery/outbox | T4 publica eventos; T8 enruta jobs sin doble efecto externo. |
| T4/T9 | métricas de outbox | T4 produce estados; T9 observa lag, age, retry y dead-letter. |
| T4/T13 | migración/evidence | T13 prueba expand/backfill/enforce y no certifica sin SHA bound. |
| T5/T13 | Playwright/realtime | T5 entrega cliente recuperable; T13 prueba dos hoteles/sesiones y fallos. |
| T6/T8 | pool/worker concurrency | T6 fija presupuesto; T8 no crea servicios extra sin necesidad. |
| T6/T9 | readiness/pool telemetry | T6 define límites; T9 los expone y no declara capacidad no medida. |
| T6/T13 | load thresholds | T6 aporta límites locales; T13 los aplica sólo en staging autorizado. |
| T7/T8 | storage/jobs | T7 deja metadata y reconciliación; T8 procesa jobs idempotentes. |
| T7/T10 | stored objects/restore | T7 no borra; T10 verifica metadatos y blobs en copia aislada. |
| T7/T13 | archivos/evidence | T13 cubre orphans/checksum sin cargar datos reales. |
| T8/T9 | heartbeats/health | T8 emite heartbeats; T9 reporta worker stale sin tumbar API opcional. |
| T8/T13 | queues/load | T13 prueba backpressure y stop thresholds. |
| T9/T13 | logs/attestation | T9 evita PII; T13 sólo empaqueta evidencia verificable. |
| T10/T13 | restore/release gate | T10 bloquea si restore falla; T13 exige resultado antes de release. |
| T11/T13 | GCP validator/evidence | T11 valida estático; T13 marca provider-bound como pendiente sin recursos. |
| T12/T13 | SLO/analytics gate | T12 no activa warehouse; T13 no reclama escala analytics. |

### Self-consistency per task

| Tarea | Text agrees with itself? | Resultado |
|---|---|---|
| T0 | Sí | Docs/manifest sin migración; rollback documental. |
| T1 | Sí | Claims validation, policy y tests cubren la misma frontera. |
| T2 | Sí | Endpoint bounded, tenant-scoped y sin payload. Implementado en `0fc3f49`. |
| T3 | Sí | Ports/client/flags y fallback tienen contrato coherente. |
| T4 | Sí | Expand/backfill/enforce y rollback forward-only son compatibles. |
| T5 | Sí | Cursor/gap/offline/revalidation reflejan el mismo contrato. |
| T6 | Sí | Pool y medición quedan condicionados al presupuesto real. |
| T7 | Sí | Dual-read y cleanup diferido protegen blobs. |
| T8 | Sí | Queues/retries/dedupe y un worker inicial son compatibles. |
| T9 | Sí | Live/ready/datastores distinguen crítico de opcional. |
| T10 | Sí | Verificador local bloquea restore incompleto. |
| T11 | Sí | Portabilidad sin provisionamiento ni apply. |
| T12 | Sí | Gate medible y decisión diferida. |
| T13 | Sí | Datos sintéticos, stop thresholds y evidencia SHA-bound alineados. |

## Rulings

Ruling: ejecutar primero T0, luego T1/T3/T6/T7/T9/T10/T11/T12 como bases
independientes y T4/T5/T8/T13 respetando sus dependencias; esto reduce
conflictos de archivos y permite revisar cada contrato antes de consumirlo. Si
fuera incorrecto, habrá reordenamiento o cherry-pick local, pero no se altera
el checkout original.

Ruling: implementar sólo capacidades provider-bound en forma de adaptadores,
validadores y pruebas fake/locales; no provisionar, facturar, autenticar
OAuth externo, cargar, restaurar ni hacer cutover remoto. Esto preserva el
límite de costo cero; el costo si se equivoca es dejar gates operativos
pendientes para aprobación humana.

Ruling: el push directo a `origin/main` se reserva para el final y sólo se
ejecuta con suite/validadores verdes y rama limpia; no se hará force-push. Si
branch protection lo impide, se conserva la rama y se entrega el motivo.

## Task status

Task 0: complete (commit 4c7ec61, reviewer CLEAN, focused tests 7 passed)
Task 1: complete (commit 50f02d8; self-review clean; auth tests 43 passed; frontend typecheck pending node_modules)
Task 2: complete (commit 0fc3f49, verified in prior turn)
Task 3: complete (commit 4cbb226; focused ephemeral/lock/cache/health tests 38 passed; collaboration migration remains a follow-up)
Task 4: complete (commit 078e798; focused outbox/recovery/migration tests 18 passed; sequence enforcement remains a follow-up)
Task 5: complete (commit e562e7e; focused realtime tests 31 passed; frontend dependency/E2E and long-lived membership revalidation remain provider/browser gates)
Task 6: complete (commit 3c0704b; focused database/security/realtime tests 48 passed; provider connection budget remains needs-verification)
Task 7: complete (commit 02908b1; focused storage/payment/company/analytics tests 37 passed; GCS provider and legacy reconciliation remain provider-bound)
Task 8: complete (commit 7667a6b; dispatcher/heartbeat/schedule tests 12 passed; worker runtime and provider metrics remain provider-bound)
Task 9: complete (commit 24b1c28; health/security tests 13 passed; provider metrics and alerting remain provider-bound)
Task 10: complete (commits fc940df and 3b19096; local restore/object verification tests 60 passed; provider-bound restore remains blocked pending signed human drill)
Task 11: complete (commit f3d99b6; static GCP readiness validator passes; no provider resources provisioned)
Task 12: complete (commit f3d99b6; analytics gate documented; no warehouse/NoSQL activation)
Task 13: complete (current worktree; local release checklist/load runner/static CI gate added; provider-bound QA/restore/load/signature remain blocking)
