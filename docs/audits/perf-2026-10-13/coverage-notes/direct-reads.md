# Lecturas directas de cierre de cobertura (frontend)

Archivos que el lector de la parte 7 declaró haber leído solo por tramos (o no haber leído) y los pequeños de `frontend/` que ninguna nota mencionaba. Los leí **completos** yo mismo, línea por línea. Etiquetas como en `REPORT.md` § 0.3.

| Archivo | Líneas | Lectura |
|---|---:|---|
| `frontend/src/api/client.ts` | 821 | completa |
| `frontend/src/api/queryKeys.ts` | 252 | completa |
| `frontend/src/state/session.tsx` | 416 | completa |
| `frontend/src/ui/AppShell.tsx` | 680 | completa |
| `frontend/src/styles/tailwind.css` | 289 | completa |
| `frontend/src/config/publicUrls.ts` | 80 (primeras) | tramo relevante (`isAppHostname`) |
| `frontend/public/sitemap.xml` | 12 | completa |
| `frontend/public/robots.txt` | 17 | completa |
| `frontend/src/utils/cashExpenseValidation.d.mts`, `largeTotalAdjustment.d.mts`, `roomBlockVisibility.d.mts` | 6 + 4 + 3 | completas |
| `frontend/postcss.config.cjs`, `frontend/tsconfig.node.json` | 6 + 10 | completas |
| `frontend/CAPACITOR_RELEASE.md` | 66 | completa |
| `frontend/public/fonts/*.woff2` (4), `public/marketing/screenshots/*.webp` (12) | binarios | caracterizados con `wc`/cabeceras (ver abajo); no son legibles como texto |
| `frontend/package-lock.json` | 252 kB | analizado con `python3 -I` (estructura, conteos) |

## `api/client.ts` (821 líneas, leído completo)

- ✔ **Un 401 de negocio cierra la sesión con recarga completa.** `requestWithRefresh` (`client.ts:653-701`) intenta `refreshSession` ante cualquier `401` de una ruta no pública (excepto el rechazo de TOTP en `/api/auth/step-up`, `:482-488`); si el refresh sale bien reintenta con `allowRefresh=false`, y si el reintento vuelve a dar `401`, `handleUnauthorized` (`:339-348`) vacía la sesión y hace `window.location.assign("/login?expired=1")`. Los endpoints `mfa/disable` y `mfa/recovery-codes/regenerate` responden `401` por código TOTP o contraseña incorrectos (`app/api/auth.py:1489,1500,1532`) y no están exceptuados: **un error de tipeo cierra la sesión**, tras 2 requests extra (refresh + reintento). Coincide con la nota de la parte 5. → `REPORT.md` F17.
- ✔ `API_BASE` por defecto es `http://127.0.0.1:8040/api` (`:79-81`): si el build de producción no define `VITE_API_URL`, el navegador llama a `localhost`. Es una trampa de despliegue (la documenta `CAPACITOR_RELEASE.md`); el valor real de Vercel es `needs-verification` (○).
- ✔ Cada request (también los `GET`) fija `Content-Type: application/json` y `Authorization`/`X-Hotel-Id`/`X-User-Id` (`:408-429`): todo request cross-origin hace preflight; `X-User-Id` no lo lee el backend.
- ✔ Cada mutación genera un UUID (`crypto.randomUUID`) para el eco SSE, **pero no una `Idempotency-Key`** (F14): el timeout de 60 s devuelve `408` "no se pudo confirmar" y el reintento queda a cargo del usuario.
- ✔ Timeouts: 20 s lecturas, 60 s mutaciones (`:68-69`) con `Promise.race` y `AbortController`; el refresh tiene su propio timeout de 20 s (`:531`), independiente del plazo del request original.
- ✔ Refresh coalescido con `navigator.locks` y reintento por carrera de rotación de cookie (`:518-594`): bien resuelto.
- [info] El módulo guarda ~10 variables globales de módulo (sesión, step-up, refresh); funciona porque hay una sola sesión por pestaña.

## `api/queryKeys.ts` (252 líneas, leído completo)

- ✔ 23 constructores en `queryKeys` y 80+ prefijos en `HOTEL_ID_INDEX_BY_QUERY_PREFIX`; la posición del `hotelId` no es uniforme (`reports`, `permissions`, `settings-security` lo llevan en el índice 2: `:123,110,130`), de ahí el mapa de excepciones.
- ✔ `QUERY_PREFIXES_BY_DOMAIN` (`:152-244`): el dominio `analytics` refresca `analytics` **y** `reports` (`:153-156`): confirma F3 (toda escritura que emite `analytics` re-pide los reportes activos).
- ✔ **Prefijos repetidos en dos dominios** (una escritura que emite ambos los invalida dos veces): `occupancy-grid` y `reservation-quote` (`reservations` y `rooms`), `payment-summary` (`payments` y `reservations`), `permissions-matrix` (`security` y `settings`), `notification-preferences` y `daily-report-schedules` (`settings` y `notifications`). Como `invalidateQueries` cancela el refetch en vuelo por defecto, la grilla de ocupación puede pedirse dos veces por evento (○: no medido).
- ✔ El dominio `whatsapp` solo contiene `whatsapp-conversations` (`:243`); la mutación de WhatsApp invalida `["whatsapp","conversations",…]`, que no coincide (nota parte 3/5).

## `state/session.tsx` (416 líneas, leído completo) y `config/publicUrls.ts`

- ✔ **Corrección a F2:** `shouldRestoreInitialSession()` (`session.tsx:139-146`) es `true` en **cualquier ruta del host de la app** (`app.hotels-pms.com`, hosts de vista previa solo con `VITE_ALLOW_PREVIEW_APP_HOST`, y shells nativos), salvo `/adminpmsmaster`, `/login?sessionRecovery=1` y `/login` sin CSRF guardado. No hace falta tener sesión: un visitante nuevo de `/register-owner`, `/forgot-password` o `/invitations/accept` también espera a `POST /api/auth/session/refresh` (que le responde `401`) antes de ver el formulario. El host de marketing (`hotels-pms.com`) no restaura sesión.
- ✔ `userId` de la sesión **es el email** (`session.tsx:155-156`): sirve como discriminante de claves de caché (S23 usa `session.userId`).
- ✔ `logout()` (`:218-229`) no vacía el `QueryClient`; los cuatro llamadores voluntarios navegan sin recargar (`UserBadge.tsx:23-26`, `SettingsSecurityPage.tsx:73`, `SettingsSessionsPage.tsx:31`, `AcceptInvitationPage.tsx:321`) ⇒ F5 confirmado. **Matiz:** la salida por `401` sí hace `window.location.assign`, que descarta la memoria; el riesgo es solo del logout voluntario.
- ✔ `value` del contexto se recrea en cada render y `setHotelId`/`setRole` no están en `useCallback` (`:356-366`); con `setPermissions` que crea sesión nueva en cada llamada (`:343-352`) todo consumidor de `useSession()` re-renderiza (F16).
- ✔ Restauración: 3 intentos de 20 s con esperas de 0,5 y 1,5 s ⇒ peor caso 62 s (`:45,294-300`).

## `ui/AppShell.tsx` (680 líneas, leído completo)

- ✔ `ReservationDetailDrawer` se importa estático (`:7`) y se monta siempre que haya `reservation:create` o `checkin:perform` (`:673-675`); `NotificationsPanel` también va estático (`:6`) pero **no** consulta mientras está cerrado (`useNotificationsInbox(…, open)`, `NotificationsPanel.tsx:53`).
- ✔ El shell dispara 6 lecturas propias: `useEffectivePermissions` (`:171`), `useUnreadNotificationCount` → `GET notifications?limit=1` (`:182`), `useHotelConfig` (`:189`), `useHotelInterfaceLanguage` (`:190`), `useOnboardingStatus` (solo owner/co-owner con `hotel_settings:update`, `:192-198`) y `useSubscriptionStatus` (salvo housekeeping, `:199`), más `useCrossTabSync` (recovery + stream, `:185`).
- ✔ `filterItems` (`:226-235`) depende de `hasAnyPermission`/`hasAllPermissions`/`hasPermission`, que `usePermissions` recrea en cada render: el `useMemo` nunca se reutiliza. Los ítems con `minPlan` se ocultan si `subscription?.plan` es indefinido (`:233`).
- ✔ `ReservationGlobalSearch`, `HotelSelector` y `UserBadge` se montan dos veces (cabecera de escritorio `:549-570` oculta por CSS en móvil, y panel móvil `:648-652` al abrirlo).
- [info] El `<details>` del menú es nativo (sin estado JS); el resto de la barra y los banners son baratos.
- ○ La campana (`notifications?limit=1`) se refetchea en cada evento de dominio `notifications`; es una explicación plausible, **no verificada**, de las 182 llamadas en 49 min que midió QA (O9).

## `styles/tailwind.css` (289 líneas, leído completo)

- ✔ Fuentes autoalojadas con `font-display: swap` y partidas por `unicode-range` (latin / latin-ext): el navegador baja `*-latin-ext` solo si hace falta. `Archivo Variable` (eje de ancho 62–125 %, 90 kB + 86 kB) se usa solo para titulares (`.display-wide`).
- ✔ Transiciones globales de 150 ms sobre `a, button, input, select, textarea` (`:88-98`) y reglas `min-height: 44px` móviles: bajo costo.
- [P2] **LCP del sitio de marketing:** `[data-seq]` arranca con `opacity: 0` y una animación `forwards` con retraso `--i × 70 ms + --seq-offset` (`:237-242`); si el titular o la imagen principal llevan `data-seq`, el LCP se retrasa esa cantidad (sin medir; ○).
- [info] Sin `@import` de fuentes remotas: la hoja de Google Fonts viene de `index.html:97-101` (F12).

## Archivos pequeños

- `public/sitemap.xml`: 9 URL con `changefreq`/`priority` (Google los ignora), sin `lastmod`; coincide con las 9 rutas de `frontend/vercel.json`. `public/robots.txt`: bloquea las rutas autenticadas y declara el sitemap ✔.
- `tsconfig.node.json`: `include: ["vite.config.ts"]`, pero el archivo es **`vite.config.mjs`**: la referencia de `tsconfig.json:18` compila un archivo inexistente (config obsoleta, [P2], ✔).
- `postcss.config.cjs`: Tailwind + Autoprefixer, estándar.
- `.d.mts` (3): declaraciones de tipos de utilidades `.mjs`; correctas y mínimas.
- `CAPACITOR_RELEASE.md`: guía de publicación móvil; confirma que `assets/icon.png` y `splash.png` son 512×512 (Apple exige 1024×1024) y que **la app móvil nativa no está publicada ni es necesaria para el piloto** (`frontend/ios` + `frontend/android` ≈ 35 MB en el repo).

## Binarios y lockfile (caracterizados, no leídos como texto)

- Fuentes `public/fonts/*.woff2` (4): 48.432 + 85.272 + 90.096 + 85.856 = **309.656 B**; cabecera `wOF2` válida.
- Capturas `public/marketing/screenshots/*.webp` (12): **715.028 B** en total; escritorio 2160×1350 (≈ 70–117 kB c/u) y móvil 585×1266 (≈ 25–35 kB c/u); ya son WebP y las imágenes llevan `loading="lazy"` y `decoding="async"` (`ProductTourSection.tsx:54-77`) ✔ (lo que sí pesa en imágenes son los PNG de marca, F12).
- `package-lock.json`: `lockfileVersion` 3, **508 paquetes** (66 de producción, 391 de desarrollo, 50 opcionales); 18 nombres con más de una versión (`semver`, `glob`, `minimatch`, `rimraf`, `debug`…). Nada anómalo.
