# Inventario completo — backend (`app/`) y frontend (`frontend/src/`)

Generado con AST (backend) y `wc -l` (frontend) sobre el commit `ef0aa41`. Cobertura: **todos** los archivos versionados.

Columnas backend: LOC = líneas del archivo; fn = funciones/métodos; db = sitios de acceso a DB (`db.query/get/execute…`); N+1 = llamadas a DB dentro de bucles (heurístico); `.all()` s/lím = `.all()` sin `.limit()`; commits = `commit()` totales.


## Dónde está la lectura de cada archivo

Este inventario es la tabla de **métricas** (AST y `wc -l`). La **lectura** de cada archivo, con sus hallazgos, está en:

| Zona | Archivos | Notas de lectura |
|---|---:|---|
| `app/` (modelos, servicios, API, esquemas, tareas, adaptadores, panel master, middleware, scripts) | 375 | [`LECTURA-COMPLETA.md`](LECTURA-COMPLETA.md) (incluye la tabla final de verificación empírica) |
| `frontend/src/` — reservas | parte 1 | [`frontend-notes/part-1.md`](frontend-notes/part-1.md) |
| `frontend/src/` — páginas grandes, `api/` y hooks de huéspedes/caja/stock/lavandería | parte 2 | [`frontend-notes/part-2.md`](frontend-notes/part-2.md) |
| `frontend/src/` — tarifas, asistente, operación, reportes, ajustes | parte 3 | [`frontend-notes/part-3.md`](frontend-notes/part-3.md) |
| `frontend/src/` — onboarding, vistas públicas, panel master, marketing, estilos | parte 4 | [`frontend-notes/part-4.md`](frontend-notes/part-4.md) |
| `frontend/src/api/*` y `hooks/*` (cliente HTTP, evento→query, SSE) | parte 5 | [`frontend-notes/part-5.md`](frontend-notes/part-5.md) |
| `frontend/src/locales/*`, `i18n.ts`, `main.tsx` | parte 6 | [`frontend-notes/part-6.md`](frontend-notes/part-6.md) |
| `frontend/src/` — shell, router, sesión, `crossTabSync`, componentes compartidos, `package.json`, `vite.config` | parte 7 | [`frontend-notes/part-7.md`](frontend-notes/part-7.md) |
| `alembic/versions/` (173 migraciones, orden de aplicación) | 85 + 88 | [`migration-notes-a.md`](migration-notes-a.md), [`migration-notes-b.md`](migration-notes-b.md) |
| CI/CD, `render.yaml`, Dockerfiles, `scripts/`, `agent-ops/`, `qa/`, dependencias | 119 | [`ops-notes.md`](ops-notes.md) |

Lo que se verificó por segunda vez (y las correcciones) está en [`frontend-notes/verificacion-manual.md`](frontend-notes/verificacion-manual.md) y en las líneas `CORREGIDO (verificación)` de las notas. La síntesis, con la leyenda ✔/◐/○, es [`REPORT.md` § 0.3](REPORT.md).

## app/  (4 archivos, 1956 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| config.py | 712 | 19 | 0 | 0 | 0 | 0 |
| main.py | 641 | 19 | 0 | 0 | 0 | 1 |
| database.py | 602 | 28 | 0 | 0 | 0 | 0 |
| __init__.py | 1 | 0 | 0 | 0 | 0 | 0 |

## app/adapters  (8 archivos, 806 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| paypal_adapter.py | 202 | 6 | 0 | 0 | 0 | 0 |
| rate_limiter.py | 152 | 6 | 13 | 0 | 0 | 0 |
| mercadopago_adapter.py | 150 | 5 | 0 | 0 | 0 | 0 |
| memory_tokens.py | 138 | 7 | 11 | 0 | 0 | 1 |
| job_dispatcher.py | 119 | 4 | 6 | 0 | 0 | 0 |
| ephemeral.py | 25 | 6 | 0 | 0 | 0 | 0 |
| telemetry.py | 19 | 3 | 0 | 0 | 0 | 0 |
| __init__.py | 1 | 0 | 0 | 0 | 0 | 0 |

## app/api  (67 archivos, 22567 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| reservations.py | 2123 | 34 | 55 | 1 | 1 | 19 |
| auth.py | 1679 | 50 | 25 | 0 | 0 | 47 |
| invitations.py | 1040 | 20 | 27 | 0 | 0 | 18 |
| cash_register.py | 977 | 26 | 15 | 0 | 0 | 8 |
| bookings.py | 957 | 18 | 50 | 0 | 2 | 9 |
| users.py | 900 | 16 | 54 | 0 | 4 | 7 |
| laundry_vendor.py | 855 | 27 | 11 | 0 | 0 | 13 |
| collaboration.py | 850 | 22 | 7 | 0 | 0 | 1 |
| daily_rates.py | 818 | 14 | 32 | 0 | 0 | 7 |
| permissions.py | 797 | 30 | 12 | 0 | 1 | 11 |
| rooms.py | 780 | 21 | 86 | 4 | 10 | 8 |
| analytics.py | 631 | 28 | 0 | 0 | 0 | 12 |
| reports.py | 558 | 10 | 4 | 0 | 1 | 0 |
| integrations.py | 550 | 15 | 3 | 0 | 0 | 10 |
| operational_tasks.py | 543 | 17 | 6 | 0 | 0 | 6 |
| stock.py | 490 | 19 | 8 | 0 | 0 | 9 |
| guests.py | 434 | 15 | 16 | 0 | 0 | 7 |
| gemma_chat.py | 368 | 17 | 0 | 0 | 0 | 6 |
| fx_rates.py | 331 | 7 | 2 | 0 | 0 | 1 |
| allocation_policy.py | 330 | 16 | 0 | 0 | 0 | 7 |
| subscription.py | 277 | 12 | 4 | 0 | 0 | 6 |
| settings_security.py | 275 | 10 | 14 | 0 | 0 | 1 |
| payment_surcharges.py | 268 | 7 | 19 | 0 | 1 | 3 |
| company_documents.py | 232 | 10 | 11 | 0 | 0 | 5 |
| public_booking.py | 231 | 10 | 6 | 0 | 1 | 2 |
| companies.py | 231 | 9 | 9 | 1 | 1 | 5 |
| room_blocks.py | 227 | 7 | 3 | 0 | 0 | 3 |
| rate_change_drafts.py | 219 | 7 | 3 | 0 | 0 | 3 |
| events.py | 206 | 5 | 8 | 0 | 0 | 0 |
| whatsapp_crm.py | 202 | 8 | 8 | 0 | 0 | 5 |
| roles.py | 201 | 6 | 3 | 0 | 0 | 3 |
| commercial.py | 200 | 12 | 0 | 0 | 0 | 8 |
| onboarding.py | 198 | 11 | 1 | 0 | 0 | 10 |
| payments.py | 197 | 5 | 1 | 0 | 0 | 1 |
| checkin.py | 193 | 5 | 6 | 0 | 0 | 3 |
| notifications.py | 188 | 10 | 2 | 0 | 0 | 6 |
| movement_groups.py | 185 | 7 | 3 | 0 | 0 | 1 |
| config.py | 183 | 4 | 4 | 0 | 0 | 2 |
| health.py | 180 | 7 | 1 | 0 | 0 | 0 |
| reservation_groups.py | 163 | 3 | 1 | 0 | 0 | 2 |
| payment_link_tests.py | 163 | 5 | 3 | 0 | 0 | 4 |
| promotions.py | 155 | 7 | 4 | 0 | 0 | 4 |
| guest_restrictions.py | 149 | 6 | 9 | 0 | 1 | 2 |
| whatsapp_hooks.py | 149 | 6 | 2 | 0 | 0 | 2 |
| payment_links.py | 147 | 6 | 2 | 0 | 0 | 3 |
| payment_proofs.py | 146 | 5 | 3 | 0 | 0 | 3 |
| waitlist.py | 141 | 7 | 6 | 0 | 0 | 5 |
| laundry.py | 138 | 5 | 3 | 0 | 0 | 3 |
| whatsapp_meta_webhook.py | 130 | 5 | 3 | 1 | 0 | 1 |
| ota_webhooks.py | 106 | 6 | 0 | 0 | 0 | 1 |
| room_state_events.py | 85 | 3 | 4 | 0 | 0 | 2 |
| company_night_charges.py | 84 | 3 | 0 | 0 | 0 | 2 |
| public_marketing.py | 75 | 3 | 0 | 0 | 0 | 2 |
| demo.py | 73 | 3 | 2 | 0 | 0 | 1 |
| room_movement_groups.py | 73 | 3 | 1 | 0 | 0 | 1 |
| reservation_communications.py | 67 | 2 | 1 | 0 | 0 | 1 |
| guest_room_avoidances.py | 64 | 2 | 1 | 0 | 0 | 1 |
| hotel_api_keys.py | 59 | 3 | 2 | 0 | 0 | 2 |
| operations_audit.py | 58 | 1 | 0 | 0 | 0 | 0 |
| rate_calendar.py | 49 | 1 | 0 | 0 | 0 | 0 |
| manual_rate_access.py | 44 | 1 | 0 | 0 | 0 | 0 |
| public_inquiries.py | 37 | 1 | 0 | 0 | 0 | 0 |
| email.py | 32 | 4 | 0 | 0 | 0 | 0 |
| reference.py | 27 | 2 | 0 | 0 | 0 | 0 |
| webhook_payloads.py | 25 | 1 | 0 | 0 | 0 | 0 |
| connections.py | 23 | 1 | 1 | 0 | 0 | 1 |
| __init__.py | 1 | 0 | 0 | 0 | 0 | 0 |

## app/db  (4 archivos, 159 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| cassandra.py | 56 | 3 | 1 | 0 | 0 | 0 |
| mongo.py | 52 | 2 | 0 | 0 | 0 | 0 |
| neo4j.py | 50 | 2 | 0 | 0 | 0 | 0 |
| __init__.py | 1 | 0 | 0 | 0 | 0 | 0 |

## app/decorators  (2 archivos, 222 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| audit_hooks.py | 220 | 13 | 2 | 0 | 0 | 0 |
| __init__.py | 2 | 0 | 0 | 0 | 0 | 0 |

## app/dependencies  (3 archivos, 778 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| auth.py | 628 | 30 | 1 | 0 | 0 | 0 |
| api_key_auth.py | 148 | 4 | 3 | 0 | 0 | 3 |
| __init__.py | 2 | 0 | 0 | 0 | 0 | 0 |

## app/infrastructure  (1 archivos, 152 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| redis_backend.py | 152 | 6 | 0 | 0 | 0 | 0 |

## app/master_admin  (9 archivos, 2643 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| router.py | 652 | 25 | 27 | 0 | 1 | 23 |
| security.py | 586 | 38 | 12 | 0 | 0 | 7 |
| privacy_retention.py | 477 | 15 | 24 | 0 | 0 | 12 |
| email_provider.py | 218 | 14 | 0 | 0 | 0 | 0 |
| billing_policy.py | 208 | 7 | 4 | 0 | 0 | 0 |
| stripe.py | 198 | 10 | 3 | 0 | 0 | 0 |
| models.py | 184 | 1 | 0 | 0 | 0 | 0 |
| schemas.py | 118 | 0 | 0 | 0 | 0 | 0 |
| __init__.py | 2 | 0 | 0 | 0 | 0 | 0 |

## app/middleware  (2 archivos, 93 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| subscription.py | 92 | 2 | 0 | 0 | 0 | 1 |
| __init__.py | 1 | 0 | 0 | 0 | 0 | 0 |

## app/models  (71 archivos, 9669 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| ota_core.py | 534 | 0 | 0 | 0 | 0 | 0 |
| reservation.py | 494 | 6 | 0 | 0 | 0 | 0 |
| analytics.py | 395 | 1 | 0 | 0 | 0 | 0 |
| __init__.py | 383 | 0 | 0 | 0 | 0 | 0 |
| cash_register.py | 346 | 5 | 0 | 0 | 0 | 0 |
| allocation.py | 339 | 0 | 0 | 0 | 0 | 0 |
| commercial.py | 317 | 0 | 0 | 0 | 0 | 0 |
| operational_task.py | 287 | 0 | 0 | 0 | 0 | 0 |
| whatsapp_crm.py | 282 | 1 | 0 | 0 | 0 | 0 |
| laundry_vendor.py | 281 | 0 | 0 | 0 | 0 | 0 |
| notification.py | 259 | 1 | 0 | 0 | 0 | 0 |
| guest.py | 254 | 7 | 0 | 0 | 0 | 0 |
| operations.py | 253 | 1 | 0 | 0 | 0 | 0 |
| payment.py | 226 | 0 | 0 | 0 | 0 | 0 |
| transaction.py | 208 | 1 | 0 | 0 | 0 | 0 |
| company_night_charge.py | 181 | 0 | 0 | 0 | 0 | 0 |
| linen.py | 176 | 0 | 0 | 0 | 0 | 0 |
| promotion.py | 166 | 2 | 0 | 0 | 0 | 0 |
| hotel_config.py | 161 | 4 | 0 | 0 | 0 | 0 |
| voucher.py | 158 | 2 | 0 | 0 | 0 | 0 |
| stock.py | 155 | 0 | 0 | 0 | 0 | 0 |
| pending_action.py | 152 | 1 | 0 | 0 | 0 | 0 |
| refund.py | 142 | 1 | 0 | 0 | 0 | 0 |
| permission.py | 138 | 0 | 0 | 0 | 0 | 0 |
| room.py | 137 | 2 | 0 | 0 | 0 | 0 |
| ai_assistant.py | 128 | 0 | 0 | 0 | 0 | 0 |
| daily_rate.py | 125 | 2 | 0 | 0 | 0 | 0 |
| subscription_v2.py | 124 | 1 | 0 | 0 | 0 | 0 |
| payment_proof.py | 122 | 0 | 0 | 0 | 0 | 0 |
| waitlist.py | 110 | 1 | 0 | 0 | 0 | 0 |
| temporary_action_grant.py | 106 | 0 | 0 | 0 | 0 | 0 |
| ota.py | 105 | 2 | 0 | 0 | 0 | 0 |
| onboarding.py | 102 | 15 | 0 | 0 | 0 | 0 |
| company_document.py | 101 | 1 | 0 | 0 | 0 | 0 |
| reservation_communication.py | 100 | 1 | 0 | 0 | 0 | 0 |
| cash_expense.py | 94 | 0 | 0 | 0 | 0 | 0 |
| reservation_group_payment.py | 94 | 0 | 0 | 0 | 0 | 0 |
| hotel_api_key.py | 92 | 1 | 0 | 0 | 0 | 0 |
| room_block.py | 90 | 2 | 0 | 0 | 0 | 0 |
| guest_room_avoidance.py | 89 | 1 | 0 | 0 | 0 | 0 |
| marketing.py | 87 | 1 | 0 | 0 | 0 | 0 |
| audit_log.py | 84 | 1 | 0 | 0 | 0 | 0 |
| guest_restriction.py | 82 | 1 | 0 | 0 | 0 | 0 |
| domain_event_outbox.py | 82 | 1 | 0 | 0 | 0 | 0 |
| subscription.py | 80 | 0 | 0 | 0 | 0 | 0 |
| user.py | 70 | 1 | 0 | 0 | 0 | 0 |
| payment_receipt_email_delivery.py | 69 | 0 | 0 | 0 | 0 | 0 |
| public_inquiry.py | 65 | 0 | 0 | 0 | 0 | 0 |
| rate_change_draft.py | 63 | 0 | 0 | 0 | 0 | 0 |
| hotel_role_visibility_window.py | 62 | 0 | 0 | 0 | 0 | 0 |
| payment_surcharge.py | 62 | 1 | 0 | 0 | 0 | 0 |
| hotel_role.py | 61 | 1 | 0 | 0 | 0 | 0 |
| user_mfa.py | 61 | 0 | 0 | 0 | 0 | 0 |
| company.py | 61 | 1 | 0 | 0 | 0 | 0 |
| integration.py | 59 | 0 | 0 | 0 | 0 | 0 |
| laundry.py | 59 | 0 | 0 | 0 | 0 | 0 |
| invitation.py | 48 | 1 | 0 | 0 | 0 | 0 |
| stored_object.py | 47 | 0 | 0 | 0 | 0 | 0 |
| job_runtime.py | 47 | 0 | 0 | 0 | 0 | 0 |
| payment_link_test.py | 45 | 1 | 0 | 0 | 0 | 0 |
| hotel_membership.py | 44 | 0 | 0 | 0 | 0 | 0 |
| user_session.py | 42 | 1 | 0 | 0 | 0 | 0 |
| fx_rate_snapshot.py | 41 | 1 | 0 | 0 | 0 | 0 |
| security_audit_log.py | 39 | 0 | 0 | 0 | 0 | 0 |
| reservation_group.py | 34 | 0 | 0 | 0 | 0 | 0 |
| action_step_up_ticket_use.py | 32 | 1 | 0 | 0 | 0 | 0 |
| connection.py | 30 | 1 | 0 | 0 | 0 | 0 |
| security_token.py | 30 | 0 | 0 | 0 | 0 | 0 |
| pricing.py | 27 | 1 | 0 | 0 | 0 | 0 |
| rate_limit_event.py | 26 | 0 | 0 | 0 | 0 | 0 |
| domain_event_retention_watermark.py | 24 | 0 | 0 | 0 | 0 | 0 |

## app/schemas  (50 archivos, 5504 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| reservation.py | 349 | 13 | 0 | 0 | 0 | 0 |
| reservation_operations.py | 345 | 4 | 0 | 0 | 0 | 0 |
| cash_register.py | 312 | 4 | 0 | 0 | 0 | 0 |
| auth.py | 265 | 8 | 0 | 0 | 0 | 0 |
| analytics_api.py | 254 | 8 | 0 | 0 | 0 | 0 |
| commercial.py | 244 | 4 | 0 | 0 | 0 | 0 |
| reports.py | 239 | 0 | 0 | 0 | 0 | 0 |
| hotel_config.py | 234 | 9 | 0 | 0 | 0 | 0 |
| hotel_api_key.py | 201 | 3 | 0 | 0 | 0 | 0 |
| promotion.py | 170 | 5 | 0 | 0 | 0 | 0 |
| transaction.py | 148 | 4 | 0 | 0 | 0 | 0 |
| onboarding.py | 147 | 6 | 0 | 0 | 0 | 0 |
| room.py | 142 | 0 | 0 | 0 | 0 | 0 |
| operational_tasks.py | 138 | 2 | 0 | 0 | 0 | 0 |
| whatsapp_hooks.py | 126 | 5 | 0 | 0 | 0 | 0 |
| gemma_chat.py | 125 | 0 | 0 | 0 | 0 | 0 |
| allocation_policy.py | 116 | 0 | 0 | 0 | 0 | 0 |
| permission.py | 109 | 2 | 0 | 0 | 0 | 0 |
| booking.py | 107 | 4 | 0 | 0 | 0 | 0 |
| marketing.py | 102 | 2 | 0 | 0 | 0 | 0 |
| company_night_charge.py | 96 | 3 | 0 | 0 | 0 | 0 |
| notification.py | 96 | 1 | 0 | 0 | 0 | 0 |
| whatsapp_crm.py | 95 | 0 | 0 | 0 | 0 | 0 |
| guest.py | 93 | 0 | 0 | 0 | 0 | 0 |
| public_inquiry.py | 84 | 8 | 0 | 0 | 0 | 0 |
| analytics_insights.py | 82 | 2 | 0 | 0 | 0 | 0 |
| ota_manual.py | 78 | 5 | 0 | 0 | 0 | 0 |
| reservation_group_payment.py | 75 | 4 | 0 | 0 | 0 | 0 |
| analytics.py | 67 | 0 | 0 | 0 | 0 | 0 |
| settings_security.py | 65 | 0 | 0 | 0 | 0 | 0 |
| guest_restriction.py | 64 | 2 | 0 | 0 | 0 | 0 |
| rate_calendar.py | 64 | 0 | 0 | 0 | 0 | 0 |
| payment_link.py | 59 | 2 | 0 | 0 | 0 | 0 |
| waitlist.py | 57 | 0 | 0 | 0 | 0 | 0 |
| company_document.py | 53 | 0 | 0 | 0 | 0 | 0 |
| integration.py | 49 | 0 | 0 | 0 | 0 | 0 |
| reservation_communication.py | 48 | 0 | 0 | 0 | 0 | 0 |
| guest_tag.py | 46 | 0 | 0 | 0 | 0 | 0 |
| operational_audit.py | 43 | 0 | 0 | 0 | 0 | 0 |
| payment_proof.py | 43 | 0 | 0 | 0 | 0 | 0 |
| payment_link_test.py | 42 | 0 | 0 | 0 | 0 | 0 |
| subscription.py | 39 | 0 | 0 | 0 | 0 | 0 |
| room_movement_group.py | 38 | 0 | 0 | 0 | 0 | 0 |
| guest_room_avoidance.py | 37 | 1 | 0 | 0 | 0 | 0 |
| collaboration.py | 35 | 0 | 0 | 0 | 0 | 0 |
| connection.py | 26 | 0 | 0 | 0 | 0 | 0 |
| __init__.py | 24 | 0 | 0 | 0 | 0 | 0 |
| datetime_types.py | 15 | 1 | 0 | 0 | 0 | 0 |
| domain_event.py | 10 | 0 | 0 | 0 | 0 | 0 |
| invitation.py | 8 | 0 | 0 | 0 | 0 | 0 |

## app/scripts  (6 archivos, 637 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| repair_cash_handoff_schema.py | 316 | 3 | 0 | 0 | 0 | 0 |
| seed_demo.py | 161 | 2 | 19 | 2 | 0 | 1 |
| mock_gemma_runtime.py | 103 | 4 | 0 | 0 | 0 | 0 |
| run_notification_cycle.py | 36 | 1 | 0 | 0 | 0 | 0 |
| dev_reset.py | 20 | 1 | 0 | 0 | 0 | 0 |
| __init__.py | 1 | 0 | 0 | 0 | 0 | 0 |

## app/services  (127 archivos, 53357 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| reservation_service.py | 3189 | 57 | 82 | 1 | 4 | 0 |
| domain_events.py | 2241 | 63 | 17 | 0 | 1 | 1 |
| permission_service.py | 2187 | 49 | 108 | 7 | 14 | 2 |
| reservation_operations_service.py | 1811 | 28 | 69 | 1 | 1 | 0 |
| analytics_service.py | 1492 | 58 | 80 | 0 | 11 | 0 |
| ota_service.py | 1477 | 34 | 66 | 2 | 1 | 0 |
| payment_service.py | 1346 | 18 | 71 | 1 | 5 | 0 |
| operational_report_service.py | 1253 | 26 | 39 | 0 | 7 | 0 |
| allocation_engine.py | 1139 | 18 | 14 | 0 | 0 | 0 |
| reservation_action_service.py | 1086 | 23 | 33 | 1 | 4 | 0 |
| analytics_facts.py | 1067 | 26 | 35 | 4 | 4 | 0 |
| company_night_charge_service.py | 921 | 15 | 76 | 3 | 15 | 0 |
| rate_change_draft_service.py | 920 | 25 | 36 | 1 | 2 | 0 |
| operational_task_service.py | 819 | 27 | 49 | 0 | 4 | 0 |
| gemma_orchestrator.py | 817 | 28 | 16 | 0 | 0 | 0 |
| cash_register_service.py | 796 | 20 | 65 | 1 | 7 | 0 |
| notification_service.py | 763 | 29 | 63 | 3 | 7 | 0 |
| gemma_service.py | 735 | 33 | 0 | 0 | 0 | 0 |
| integration_service.py | 703 | 28 | 22 | 1 | 0 | 0 |
| laundry_vendor_service.py | 687 | 17 | 49 | 1 | 6 | 0 |
| stock_service.py | 684 | 22 | 61 | 0 | 6 | 0 |
| subscription_entitlements.py | 653 | 30 | 64 | 0 | 0 | 0 |
| onboarding_service.py | 650 | 24 | 18 | 2 | 1 | 0 |
| analytics_contracts.py | 628 | 24 | 1 | 0 | 0 | 0 |
| analytics_exports.py | 595 | 27 | 9 | 0 | 0 | 2 |
| pricing_service.py | 593 | 9 | 64 | 1 | 7 | 0 |
| pricing_policy_service.py | 593 | 13 | 23 | 0 | 2 | 0 |
| cash_daily_summary_service.py | 593 | 7 | 39 | 3 | 8 | 0 |
| payment_link_service.py | 591 | 23 | 25 | 1 | 3 | 0 |
| analytics_warehouse.py | 588 | 29 | 0 | 0 | 0 | 0 |
| financial_report_service.py | 573 | 11 | 26 | 0 | 8 | 0 |
| linen_service.py | 558 | 13 | 54 | 3 | 9 | 0 |
| room_movement_group_service.py | 534 | 8 | 42 | 1 | 1 | 0 |
| operational_audit_service.py | 529 | 13 | 17 | 0 | 0 | 0 |
| fx_service.py | 512 | 22 | 0 | 0 | 0 | 0 |
| rate_calendar_service.py | 511 | 9 | 32 | 0 | 8 | 0 |
| payment_link_test_service.py | 509 | 22 | 13 | 0 | 0 | 0 |
| collaboration.py | 505 | 14 | 7 | 0 | 0 | 0 |
| checkin_service.py | 492 | 10 | 31 | 0 | 1 | 0 |
| ota_manual_service.py | 481 | 12 | 14 | 0 | 0 | 0 |
| payment_webhook_service.py | 458 | 11 | 15 | 0 | 0 | 0 |
| analytics_insights.py | 438 | 12 | 0 | 0 | 0 | 0 |
| allocation_policy_service.py | 432 | 14 | 40 | 0 | 3 | 0 |
| temporary_action_grant_service.py | 421 | 14 | 27 | 2 | 2 | 0 |
| allocation_runtime_service.py | 417 | 8 | 16 | 0 | 2 | 0 |
| read_model_cache.py | 399 | 27 | 0 | 0 | 0 | 0 |
| subscription_service.py | 391 | 19 | 36 | 0 | 2 | 0 |
| payment_proof_service.py | 388 | 11 | 23 | 0 | 0 | 0 |
| guest_service.py | 388 | 14 | 15 | 0 | 1 | 0 |
| room_block_service.py | 383 | 17 | 36 | 0 | 4 | 0 |
| cash_expense_service.py | 370 | 12 | 11 | 0 | 0 | 0 |
| guest_restriction_service.py | 367 | 13 | 12 | 0 | 2 | 0 |
| analytics_ai_providers.py | 359 | 27 | 0 | 0 | 0 | 0 |
| promotion_service.py | 357 | 15 | 14 | 0 | 2 | 0 |
| gemma_action_run_service.py | 353 | 11 | 3 | 0 | 0 | 0 |
| company_document_service.py | 344 | 11 | 26 | 0 | 2 | 0 |
| user_session_service.py | 340 | 17 | 17 | 0 | 1 | 0 |
| payment_receipt_email_service.py | 333 | 9 | 15 | 0 | 0 | 3 |
| whatsapp_crm_service.py | 294 | 10 | 32 | 0 | 0 | 0 |
| reservation_group_payment_service.py | 290 | 4 | 25 | 1 | 2 | 0 |
| promotion_pricing_service.py | 288 | 4 | 3 | 0 | 0 | 0 |
| action_step_up_service.py | 280 | 8 | 6 | 0 | 1 | 1 |
| object_storage.py | 261 | 27 | 0 | 0 | 0 | 0 |
| financial_ledger.py | 259 | 10 | 16 | 0 | 0 | 0 |
| audit_timeline_service.py | 244 | 9 | 6 | 0 | 0 | 0 |
| commercial_service.py | 243 | 21 | 40 | 0 | 4 | 0 |
| staff_invitation_service.py | 240 | 4 | 11 | 0 | 0 | 0 |
| postgres_event_listener.py | 234 | 9 | 0 | 0 | 0 | 0 |
| reservation_group_service.py | 227 | 2 | 12 | 2 | 3 | 0 |
| mfa_service.py | 212 | 15 | 18 | 1 | 1 | 0 |
| reservation_communication_service.py | 208 | 6 | 10 | 0 | 1 | 0 |
| outbox_poll_cache.py | 193 | 9 | 0 | 0 | 0 | 0 |
| reservation_quote_service.py | 189 | 1 | 0 | 0 | 0 | 0 |
| outbound_http_telemetry.py | 182 | 8 | 0 | 0 | 0 | 0 |
| audit_log_service.py | 182 | 7 | 0 | 0 | 0 | 0 |
| invitation_service.py | 180 | 7 | 9 | 0 | 0 | 0 |
| laundry_missing_followup_service.py | 176 | 3 | 14 | 0 | 1 | 0 |
| marketing_service.py | 176 | 9 | 6 | 1 | 1 | 0 |
| gemma_context_service.py | 174 | 2 | 11 | 0 | 0 | 0 |
| distributed_lock.py | 173 | 8 | 1 | 0 | 0 | 0 |
| whatsapp_booking_service.py | 169 | 5 | 4 | 0 | 1 | 0 |
| hotel_service.py | 166 | 5 | 29 | 2 | 2 | 0 |
| hotel_outbound_email_service.py | 166 | 3 | 1 | 0 | 0 | 0 |
| no_show_sweep_service.py | 165 | 2 | 12 | 3 | 2 | 1 |
| public_inquiry_service.py | 162 | 6 | 1 | 0 | 0 | 7 |
| timeseries_projection.py | 160 | 10 | 3 | 1 | 0 | 0 |
| waitlist_service.py | 155 | 9 | 11 | 0 | 0 | 0 |
| analytics_fact_refresh_queue.py | 154 | 2 | 11 | 0 | 0 | 0 |
| scheduled_hotel_jobs_service.py | 149 | 2 | 3 | 0 | 1 | 2 |
| membership_service.py | 142 | 4 | 6 | 0 | 1 | 0 |
| invitation_email_service.py | 141 | 6 | 0 | 0 | 0 | 0 |
| guest_room_avoidance_service.py | 141 | 6 | 16 | 0 | 1 | 0 |
| quote_token_service.py | 141 | 6 | 0 | 0 | 0 | 0 |
| apple_auth_service.py | 136 | 5 | 0 | 0 | 0 | 0 |
| allocation_learning_service.py | 131 | 2 | 5 | 0 | 0 | 0 |
| laundry_service.py | 130 | 7 | 11 | 0 | 0 | 0 |
| tenant_context.py | 124 | 9 | 1 | 0 | 0 | 0 |
| gemma_action_catalog.py | 123 | 5 | 0 | 0 | 0 | 0 |
| graph_projection.py | 122 | 5 | 0 | 0 | 0 | 0 |
| hotel_api_key_service.py | 120 | 7 | 9 | 0 | 1 | 0 |
| external_effects_policy.py | 120 | 12 | 0 | 0 | 0 | 0 |
| guest_profile.py | 112 | 3 | 0 | 0 | 0 | 0 |
| security.py | 111 | 8 | 0 | 0 | 0 | 0 |
| jurisdiction_profile.py | 110 | 2 | 0 | 0 | 0 | 0 |
| allocation_trigger_service.py | 98 | 2 | 0 | 0 | 0 | 1 |
| timezones.py | 97 | 6 | 1 | 0 | 0 | 0 |
| room_state_service.py | 97 | 1 | 1 | 0 | 0 | 2 |
| room_catalog_service.py | 91 | 4 | 9 | 3 | 3 | 0 |
| stored_object_service.py | 88 | 3 | 6 | 0 | 0 | 0 |
| email_service.py | 87 | 9 | 0 | 0 | 0 | 0 |
| gemma_intent_service.py | 86 | 3 | 0 | 0 | 0 | 0 |
| mfa_attempt_service.py | 84 | 3 | 3 | 0 | 0 | 1 |
| hotel_configuration_service.py | 83 | 5 | 0 | 0 | 0 | 0 |
| push_adapter.py | 75 | 4 | 0 | 0 | 0 | 0 |
| analytics_freshness.py | 70 | 2 | 0 | 0 | 0 | 0 |
| laundry_remito_preflight.py | 66 | 2 | 0 | 0 | 0 | 0 |
| connection_service.py | 55 | 2 | 3 | 0 | 0 | 0 |
| demo_reset_safety.py | 49 | 2 | 0 | 0 | 0 | 0 |
| actor_label_service.py | 47 | 1 | 4 | 1 | 1 | 0 |
| service_heartbeat.py | 38 | 1 | 3 | 0 | 0 | 0 |
| csv_export_safety.py | 32 | 2 | 0 | 0 | 0 | 0 |
| encryption.py | 25 | 1 | 0 | 0 | 0 | 0 |
| user_lookup_service.py | 23 | 2 | 3 | 0 | 0 | 0 |
| room_service.py | 19 | 1 | 2 | 0 | 0 | 0 |
| audit_projection.py | 19 | 1 | 0 | 0 | 0 | 0 |
| row_locks.py | 13 | 1 | 0 | 0 | 0 | 0 |
| __init__.py | 1 | 0 | 0 | 0 | 0 | 0 |

## app/services/email  (2 archivos, 154 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| providers.py | 152 | 11 | 0 | 0 | 0 | 0 |
| __init__.py | 2 | 0 | 0 | 0 | 0 | 0 |

## app/services/ota  (4 archivos, 335 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| orchestrator.py | 160 | 9 | 3 | 0 | 0 | 0 |
| contracts.py | 131 | 11 | 0 | 0 | 0 | 0 |
| __init__.py | 22 | 0 | 0 | 0 | 0 | 0 |
| registry.py | 22 | 2 | 0 | 0 | 0 | 0 |

## app/services/ota/adapters  (4 archivos, 798 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| booking.py | 538 | 32 | 0 | 0 | 0 | 0 |
| despegar.py | 129 | 13 | 0 | 0 | 0 | 0 |
| expedia.py | 126 | 13 | 0 | 0 | 0 | 0 |
| __init__.py | 5 | 0 | 0 | 0 | 0 | 0 |

## app/tasks  (11 archivos, 1588 LOC)

| archivo | LOC | fn | db | N+1 | `.all()` s/lím | commits |
|---|---:|---:|---:|---:|---:|---:|
| analytics_tasks.py | 733 | 13 | 33 | 3 | 9 | 4 |
| ota_tasks.py | 259 | 4 | 11 | 2 | 2 | 0 |
| celery_app.py | 175 | 3 | 0 | 0 | 0 | 0 |
| report_tasks.py | 149 | 5 | 4 | 0 | 1 | 1 |
| domain_event_tasks.py | 91 | 2 | 0 | 0 | 0 | 2 |
| notification_tasks.py | 88 | 3 | 0 | 0 | 0 | 2 |
| run_scheduled_hotel_jobs.py | 44 | 1 | 0 | 0 | 0 | 0 |
| run_no_show_sweep.py | 30 | 1 | 0 | 0 | 0 | 0 |
| no_show_tasks.py | 9 | 1 | 0 | 0 | 0 | 0 |
| cleanup_tokens.py | 9 | 0 | 0 | 0 | 0 | 0 |
| __init__.py | 1 | 0 | 0 | 0 | 0 | 0 |

**Total backend:** 375 archivos · 101418 LOC · 2866 funciones · 2958 sitios DB · 69 N+1 candidatos · 231 `.all()` sin límite · 397 commits.


# Frontend (`frontend/src/`)


## src/  (4 archivos, 715 líneas)

| archivo | líneas |
|---|---:|
| router.tsx | 596 |
| main.tsx | 59 |
| i18n.ts | 43 |
| App.tsx | 17 |

## src/api  (51 archivos, 7161 líneas)

| archivo | líneas |
|---|---:|
| client.ts | 821 |
| reservations.ts | 757 |
| cashRegister.ts | 399 |
| queryInvalidation.ts | 288 |
| reports.ts | 254 |
| permissions.ts | 253 |
| queryKeys.ts | 252 |
| guests.ts | 249 |
| laundryVendor.ts | 248 |
| stock.ts | 212 |
| auth.ts | 207 |
| gemma.ts | 189 |
| onboarding.ts | 189 |
| companies.ts | 188 |
| promotions.ts | 187 |
| linen.ts | 165 |
| rate-calendar.ts | 152 |
| payments.ts | 149 |
| rooms.ts | 133 |
| operationalTasks.ts | 129 |
| notifications.ts | 128 |
| rateChangeDrafts.ts | 109 |
| guestRestrictions.ts | 96 |
| collaboration.ts | 84 |
| roomBlocks.ts | 82 |
| users.ts | 74 |
| companyNightCharges.ts | 69 |
| paymentLinkTests.ts | 67 |
| security.ts | 64 |
| operationalAudit.ts | 63 |
| waitlist.ts | 63 |
| whatsapp.ts | 63 |
| subscription.ts | 62 |
| allocationRuns.ts | 61 |
| config.ts | 60 |
| laundry.ts | 59 |
| marketing.ts | 58 |
| paymentProofs.ts | 54 |
| fxRates.ts | 51 |
| integrations.ts | 50 |
| roles.ts | 49 |
| apiKeys.ts | 42 |
| paymentLinks.ts | 42 |
| paymentSurcharges.ts | 40 |
| commercial.ts | 39 |
| reservationCommunications.ts | 34 |
| email.ts | 28 |
| publicInquiries.ts | 23 |
| categories.ts | 12 |
| queryPolicy.ts | 7 |
| timezones.ts | 7 |

## src/auth  (1 archivos, 335 líneas)

| archivo | líneas |
|---|---:|
| ActionStepUpProvider.tsx | 335 |

## src/components  (24 archivos, 6389 líneas)

| archivo | líneas |
|---|---:|
| ReservationDetailDrawer.tsx | 1949 |
| ManualOtaReservationModal.tsx | 548 |
| GuestQuickCreatePanel.tsx | 514 |
| OccupancyGrid.tsx | 452 |
| RateCalendarGrid.tsx | 401 |
| MfaSettingsCard.tsx | 374 |
| RateEditorGrid.tsx | 339 |
| NotificationsPanel.tsx | 238 |
| RateEditorMobileCards.tsx | 198 |
| LocalizedDateField.tsx | 174 |
| GuestRestrictionsPanel.tsx | 173 |
| Seo.tsx | 119 |
| AppleSignInButton.tsx | 117 |
| InfoTip.tsx | 107 |
| RestrictionOverrideModal.tsx | 101 |
| ReservationGlobalSearch.tsx | 95 |
| GoogleSignInButton.tsx | 94 |
| CheckoutStub.tsx | 82 |
| ConfirmDialog.tsx | 76 |
| IntegrationHelpDrawer.tsx | 70 |
| PasswordInput.tsx | 59 |
| PermissionGate.tsx | 43 |
| GuestRestrictionBadge.tsx | 37 |
| StatCard.tsx | 29 |

## src/components/brand  (1 archivos, 63 líneas)

| archivo | líneas |
|---|---:|
| BrandMark.tsx | 63 |

## src/components/marketing  (7 archivos, 539 líneas)

| archivo | líneas |
|---|---:|
| MarketingShell.tsx | 189 |
| EarlyAccessForm.tsx | 149 |
| Section.tsx | 60 |
| PublicButtonLink.tsx | 55 |
| MarketingIcon.tsx | 40 |
| Breadcrumbs.tsx | 29 |
| MarketingMobileCta.tsx | 17 |

## src/components/marketing/sections  (12 archivos, 645 líneas)

| archivo | líneas |
|---|---:|
| PricingSection.tsx | 160 |
| ProductTourSection.tsx | 95 |
| ModulesSection.tsx | 81 |
| HeroSection.tsx | 52 |
| StackSection.tsx | 46 |
| ProblemSection.tsx | 38 |
| IntegrationsStrip.tsx | 33 |
| FaqSection.tsx | 32 |
| DifferentiatorsSection.tsx | 31 |
| FounderSection.tsx | 29 |
| OnboardingSection.tsx | 26 |
| FinalCtaSection.tsx | 22 |

## src/components/marketing/ui  (1 archivos, 210 líneas)

| archivo | líneas |
|---|---:|
| OccupancyBoard.tsx | 210 |

## src/config  (1 archivos, 108 líneas)

| archivo | líneas |
|---|---:|
| publicUrls.ts | 108 |

## src/constants  (1 archivos, 47 líneas)

| archivo | líneas |
|---|---:|
| notificationEvents.ts | 47 |

## src/content  (2 archivos, 438 líneas)

| archivo | líneas |
|---|---:|
| marketing.ts | 338 |
| integrationHelp.ts | 100 |

## src/data  (1 archivos, 109 líneas)

| archivo | líneas |
|---|---:|
| mock.ts | 109 |

## src/hooks  (39 archivos, 3401 líneas)

| archivo | líneas |
|---|---:|
| useCollaborativeResource.ts | 462 |
| useReservations.ts | 384 |
| useGemmaChat.ts | 250 |
| useCashRegister.ts | 242 |
| useCompanies.ts | 181 |
| usePushSubscription.ts | 178 |
| useSubscription.ts | 123 |
| useNotifications.ts | 110 |
| useReports.ts | 96 |
| useGuestRestrictions.ts | 86 |
| useGuests.ts | 80 |
| useDialogA11y.ts | 79 |
| useInstallPrompt.ts | 73 |
| usePromotions.ts | 70 |
| useIntegrations.ts | 65 |
| usePayments.ts | 65 |
| useRoomBlocks.ts | 61 |
| useRateCalendar.ts | 60 |
| usePaymentLinks.ts | 55 |
| useRooms.ts | 53 |
| useRestrictionOverridePrompt.ts | 52 |
| useHotelConfig.ts | 51 |
| useRateChangeDrafts.ts | 49 |
| usePaymentProofs.ts | 48 |
| usePaymentLinkTests.ts | 44 |
| usePermissions.ts | 44 |
| usePaymentSurcharges.ts | 43 |
| useWhatsappCRM.ts | 41 |
| useGuardedMutation.ts | 40 |
| useCompanyNightCharges.ts | 36 |
| useReservationDrawer.ts | 32 |
| useIsDesktopViewport.ts | 30 |
| useOnboardingStatus.ts | 25 |
| useOnlineStatus.ts | 22 |
| useCategories.ts | 16 |
| useOperationalAudit.ts | 15 |
| useAuthProviders.ts | 14 |
| useCountries.ts | 13 |
| useTimezones.ts | 13 |

## src/locales/en  (8 archivos, 2008 líneas)

| archivo | líneas |
|---|---:|
| reservations.json | 1244 |
| guests.json | 184 |
| rooms.json | 129 |
| appshell.json | 128 |
| common.json | 126 |
| dashboard.json | 93 |
| auth.json | 79 |
| companies.json | 25 |

## src/locales/es  (8 archivos, 2008 líneas)

| archivo | líneas |
|---|---:|
| reservations.json | 1244 |
| guests.json | 184 |
| rooms.json | 129 |
| appshell.json | 128 |
| common.json | 126 |
| dashboard.json | 93 |
| auth.json | 79 |
| companies.json | 25 |

## src/master_admin  (3 archivos, 483 líneas)

| archivo | líneas |
|---|---:|
| api.ts | 183 |
| session.tsx | 152 |
| layout.tsx | 148 |

## src/master_admin/pages  (9 archivos, 1805 líneas)

| archivo | líneas |
|---|---:|
| PrivacyRetentionPage.tsx | 440 |
| PricingPage.tsx | 259 |
| LeadsPage.tsx | 252 |
| StripePage.tsx | 169 |
| LoginPage.tsx | 166 |
| DashboardPage.tsx | 158 |
| BillingPage.tsx | 157 |
| EmailPage.tsx | 133 |
| AuditPage.tsx | 71 |

## src/state  (2 archivos, 447 líneas)

| archivo | líneas |
|---|---:|
| session.tsx | 416 |
| pendingOwner.ts | 31 |

## src/styles  (1 archivos, 289 líneas)

| archivo | líneas |
|---|---:|
| tailwind.css | 289 |

## src/sync  (2 archivos, 777 líneas)

| archivo | líneas |
|---|---:|
| crossTabSync.ts | 739 |
| retryPolicy.ts | 38 |

## src/ui  (4 archivos, 937 líneas)

| archivo | líneas |
|---|---:|
| AppShell.tsx | 680 |
| HotelSelector.tsx | 100 |
| UserBadge.tsx | 99 |
| BottomNav.tsx | 58 |

## src/utils  (7 archivos, 378 líneas)

| archivo | líneas |
|---|---:|
| paymentReceiptHtml.ts | 106 |
| date.ts | 104 |
| roomMove.ts | 61 |
| currency.ts | 45 |
| reservationStatus.ts | 29 |
| escapeHtml.ts | 21 |
| csvCell.ts | 12 |

## src/views/onboarding  (1 archivos, 1719 líneas)

| archivo | líneas |
|---|---:|
| OnboardingWizard.tsx | 1719 |

## src/views/protected  (31 archivos, 26148 líneas)

| archivo | líneas |
|---|---:|
| ReservationsPage.tsx | 6120 |
| LaundryPage.tsx | 2448 |
| StockPage.tsx | 1846 |
| CashRegisterPage.tsx | 1503 |
| SettingsHotelPage.tsx | 1296 |
| SettingsPermissionsPage.tsx | 1198 |
| GuestsPage.tsx | 1133 |
| RateCalendarPage.tsx | 984 |
| PromotionsPage.tsx | 851 |
| CompaniesPage.tsx | 821 |
| RoomsPage.tsx | 760 |
| SettingsAssistantPage.tsx | 673 |
| OperationalTasksPage.tsx | 670 |
| ReportsPage.tsx | 631 |
| SettingsConnectionsPage.tsx | 611 |
| SettingsUsersPage.tsx | 576 |
| DashboardPage.tsx | 528 |
| SettingsNotificationsPage.tsx | 447 |
| SettingsSecurityPage.tsx | 429 |
| WaitlistPage.tsx | 416 |
| SettingsTestsPage.tsx | 407 |
| TaxPoliciesCard.tsx | 353 |
| OccupancyPlanningPage.tsx | 336 |
| SettingsSubscriptionPage.tsx | 325 |
| SettingsApiKeysPage.tsx | 235 |
| HousekeepingTodayPage.tsx | 180 |
| SettingsSessionsPage.tsx | 132 |
| OperationalAuditPage.tsx | 93 |
| WhatsAppInboxPage.tsx | 68 |
| SettingsWhatsAppPage.tsx | 56 |
| SettingsMySecurityPage.tsx | 22 |

## src/views/protected/analytics  (1 archivos, 1361 líneas)

| archivo | líneas |
|---|---:|
| AnalyticsPages.tsx | 1361 |

## src/views/public  (17 archivos, 2573 líneas)

| archivo | líneas |
|---|---:|
| AcceptInvitationPage.tsx | 476 |
| LoginPage.tsx | 321 |
| TermsPage.tsx | 284 |
| ResetPasswordPage.tsx | 277 |
| PrivacyPage.tsx | 252 |
| VerifyEmailPage.tsx | 173 |
| ContactPage.tsx | 160 |
| RegisterOwnerPage.tsx | 128 |
| PmsHoteleroPage.tsx | 103 |
| SoftwareParaHotelesPage.tsx | 101 |
| FaqPage.tsx | 83 |
| MarketingHomePage.tsx | 67 |
| ThankYouPage.tsx | 49 |
| FunctionsPage.tsx | 34 |
| MarketingNotFoundPage.tsx | 29 |
| PricingPage.tsx | 24 |
| ForgotPasswordPage.tsx | 12 |

**Total frontend/src:** 239 archivos · 61093 líneas.
