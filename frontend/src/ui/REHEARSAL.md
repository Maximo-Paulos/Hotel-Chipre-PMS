# Rehearsal: Hotels-PMS mobile operator shell

## Gold and adapted method

Gold: the user's supplied mobile hospitality design guide. It calls for one-handed use, a clear persistent five-slot navigation, 48px touch controls, a warm neutral surface, role identity, and access to the complete feature set without horizontal scrolling.

Adapted StageShow references: `framing.md` shaped the real app frame and focal order; `craft.md` shaped the compact navigation, spacing and single outline-icon family; `verify.md` and `rehearse.md` drove the width checks and screenshot review; `review.md` informed the fresh-eye pass. The work stays inside the existing routed PMS shell. StageShow's `.ss-stage` demo kit and animated `film.mjs` gate do not apply to this static, data-driven product screen, so Playwright captured the real app with synthetic API responses instead.

## Composition and changes

- Mobile frame: logo/home on the left, current route title centered, alerts and compact role identity at the right.
- Navigation: four role-prioritized shortcuts plus “Más”; every link still passes through the existing permission and plan filters, and the full filtered route directory remains in the drawer.
- Touch: bottom navigation items render at 64px high; the main mobile controls and drawer links use at least 48px. Dashboard's primary and secondary actions are set to 52px and 48px on mobile. Safe-area padding remains in place.
- Surfaces: the shell uses a quiet warm sage/bone neutral while the PMS teal brand remains unchanged. Existing business content and desktop sidebar remain intact.
- No route, API, auth, permission, session, or persistence behavior changed.

## Captured frames and checks

Captured in a local Vite build with a synthetic owner login and read-only mocked API responses; no cloud service or hotel data was touched. The temporary screenshot files were reviewed during this task and are not included in the repository. Those frames predate the final dashboard action sizing adjustment.

- Reviewed frames: mobile opening and “Más” drawer at 390×844; desktop dashboard at 1280×800.
- Mobile document/body width: 390/390px; five bottom navigation targets measured 78×64px; bar measured 65px including its border.
- Drawer scroll: 1,342px of scroll in a 2,113px region; the last settings link (“Notificaciones”) is visible at the end.
- Escape closes the drawer and restores focus to the “Más” trigger.
- Desktop document/body width: 1,280/1,280px; sidebar width: 288px.
- Browser page errors: none.
- A follow-up local Playwright login fixture reached the dashboard route but landed on the permission gate because it did not provide the full effective permission set. The updated 52px/48px action bounding-box assertions are in the responsive smoke test; their browser measurements were not produced by that fixture.

## Fresh-eye review

Parent review: mobile has no horizontal overflow; the four shortcuts and “Más” read clearly; the drawer is visually distinct; desktop keeps its sidebar. The drawer end-of-list and Escape/focus restoration were then checked with Playwright.

## Limits

The screenshots use synthetic API responses and confirm visual layout and shell navigation only. They do not prove deployed cloud behavior, live hotel data, every product route, or all operator roles. The repository E2E config requires an explicitly isolated PostgreSQL app and seed database; the E2E suite was not run, and that requirement was not bypassed for this visual review.

## Rehearsal: mobile operational screens

### Gold and adapted StageShow method

Gold: the user's mobile hospitality guide: one-handed operation, 48px minimum touch targets, 52px primary actions, clear plain-language labels, warm neutral surfaces, and compact views without page-level horizontal scrolling. StageShow's `framing.md` guided the audit to start at 390×844 and keep each route's most important task visible; `craft.md` guided touch target sizing and content flow; `verify.md`, `rehearse.md`, and `review.md` guided before/after capture, measurements, and a fresh-eye pass. The real PMS routes and role guards were retained; no StageShow demo components or motion were added.

### Screens and visual changes

Reviewed Planilla, Reservas, Habitaciones, Caja, Limpieza de hoy, and Tareas at 390×844, then at 1280×800 with a synthetic owner session and read-only API fixtures.

- Planilla reservation cells now have a 48px minimum height to make repeated stay cells easier to tap.
- Caja diaria now separates its heading from the date/currency/export controls and gives those fields a responsive grid so the title and help text do not collapse into a narrow column on desktop.
- Tareas allows the task summary and its actions to wrap on small screens; task actions no longer widen the page beyond the viewport.
- The visual fixture hides the unhealthy realtime banner only inside its local browser context so that mock connectivity noise does not obscure screenshots. The product's realtime status behavior is unchanged.

### Evidence and limits

The before/after screenshots were captured from the local Vite app at 390×844 and 1280×800, with synthetic data and blocked mutations. They are task-local review artifacts and are not cloud evidence. The synthetic run observed no browser exceptions and made no backend writes. Focused Playwright assertions were added for planilla touch height, Caja heading width, and mobile task-page overflow.

No PostgreSQL-backed E2E, cloud deployment, live hotel data, payment workflow, or provider behavior was verified in this visual rehearsal. The full role matrix and every downstream state on these routes remain outside this pass.
