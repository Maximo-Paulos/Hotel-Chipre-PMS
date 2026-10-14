# Auditoría de consumo — frontend, parte 3: resto de vistas protegidas

Fecha de lectura: 2026-10-14. Rutas relativas a `/home/user/Hotel-Chipre-PMS/frontend` salvo que diga `app/` (backend). Commit base: `84b4373`.
Archivos leídos COMPLETOS con Read (en tramos de ≤ 700 líneas): los 23 de la lista `fe-part-3.txt` (ver cuadro al final). Para verificar afirmaciones leí además fragmentos de `src/main.tsx`, `src/api/{client,queryKeys,queryInvalidation,queryPolicy,rate-calendar,promotions}.ts`, `src/hooks/{useRateCalendar,useRateChangeDrafts,usePromotions,useCompanies,useRooms,useGuardedMutation}.ts` y de varios routers del backend.

Convenciones: [P0] pérdida de datos/seguridad/caída · [P1] impacto alto en consumo o correctitud · [P2] mejora menor · [info]. "(verificado: archivo:línea)" = visto en el código; "(inferido, no verificado)" = deducción.

Contexto global verificado (reutilizado de las partes 1-2): `QueryClient` con `staleTime: 30_000`, `refetchOnWindowFocus: false`, 1 reintento solo en errores no-4xx (`src/main.tsx:17-30`). Todas las páginas de esta parte son `lazy()` en `src/router.tsx` (líneas 77-133) y cada ruta está envuelta en `PermissionGate` (`src/router.tsx:262-302`).
`refreshSettingsState` (usado por las mutaciones de promociones, empresas, usuarios, suscripción, etc.) invalida los dominios `settings` + `security` + `analytics` = 14 + 9 + 2 prefijos de query (`src/api/queryInvalidation.ts:refreshSettingsState`, `src/api/queryKeys.ts:QUERY_PREFIXES_BY_DOMAIN`), con `refetchType: "active"`: solo refetchea lo que esté montado, pero cambiar una promoción marca como obsoletas `permissions-*`, `operational-audit`, `analytics` y `reports` sin relación causal (verificado: queryInvalidation.ts / queryKeys.ts).

---

## 1. Notas por archivo

