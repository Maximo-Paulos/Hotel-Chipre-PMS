# Playwright cloud QA — round 2

- Date: 2026-11-06, America/Argentina/Buenos_Aires
- Application: `https://app.hotels-pms.com`
- Deployed build observed before fixes: `be604c6dc4077431fafe13c5c857fbac3b59fe9e`
- Browser: three separate signed-in Chrome profiles; owner, manager, and receptionist roles
- Method: Playwright locators and DOM snapshots against the visible cloud application
- Scope: Hotel 4; no provider dashboards, external payments, messages, OTA actions, or guest PII copied into this record

## Verified in this pass

- Analytics: period comparison and year-over-year comparison rendered for the owner; the earlier “comparison missing” finding did not reproduce.
- Reservations: selecting `Check-in` filtered the list to the one matching reservation; clearing filters restored the full 38-row list.
- Availability: category `Doble Baño Compartido`, 2026-11-06 through 2026-11-07 returned 12 available rooms.
- Occupancy agenda: switching between week and month views worked.
- Planilla: category ordering, advancing 14 days, and returning to today worked; availability by category rendered for the two-week range.
- Tasks: created a synthetic maintenance task, added a follow-up comment, opened history, and resolved it. The history showed creation, comment, and resolution; open count returned to zero.
- Laundry: the page loaded its vendor, rates, linen types, initial counts, locations, remitos, and current vendor balance. No outbound contact or inventory mutation was performed in this pass.
- Housekeeping: manager role could read the page, but the state selector for the QA room was disabled. No cleaner account was available in the three authenticated profiles to exercise the write path.

## Findings and suggestions

1. **Tariff recommendation rejects a quote that the settings page just reported saved.** Saving the official ARS/USD quote reported success, but evaluating recommendations returned “No hay una cotización USD reciente seleccionada para el hotel”. The stored market update time was older than 24 hours even though the PMS had just received the response. The recommendation selector used `provider_updated_at` for freshness. The project decision log says freshness must use the PMS receipt time (`fetched_at`) and retain the provider timestamp as provenance. **Fix in progress:** selection now orders and validates by `fetched_at`; a regression test covers an old provider timestamp on a recently received snapshot. Re-test on the deployed build before accepting the fix.

2. **Analytics freshness badge calls the oldest included fact “delay”.** The badge showed an oldest-data timestamp and 76.9 hours of “atraso”, although that value is not a source-refresh watermark and does not prove that the current report is stale. **Fix in progress:** replace the delay claim with “oldest included data updated” in Spanish and English, without changing the API contract. Re-test on the deployed build.

3. **CBC category settings contain implausible values, but the card mirrors the stored fields.** The card showed occupancy `85000` and base nightly price `4`; opening Edit showed price `4` in the base-price input and `85000` in the occupancy input. This is not a card-rendering swap. The intended correction is unknown, so no hotel values were changed. **Suggestion:** verify the intended capacity and base price with the hotel owner, then correct the record; keep the effective daily tariff separate.

4. **Category edit numeric inputs had no visible labels.** The two adjacent values were easy to misread as swapped, and the inputs had no accessible name. **Fix in progress:** add visible labels and accessible names for “Precio base por noche” and “Ocupación máxima”; add focused browser coverage.

## Validation boundary

- The cloud observations above are manual UI evidence from Playwright. They were against deployed `be604c6`; they do not validate the fixes yet.
- Code changes are in the isolated integration worktree. Frontend unit/i18n tests, lint, typecheck, and build passed after the label changes; the focused backend recommendation test passed 14 cases and Ruff passed.
- Local E2E `--list` was stopped by the repo's required PostgreSQL 16 isolated app/seed URL guard; no SQLite fallback was used. The actual cloud Playwright run was performed directly in the three signed-in profiles.
- No production tariff, category value, reservation, guest record, or payment was changed in this round. The task record is synthetic and resolved.

## Post-fix Playwright retest (`code_sha` `b76d07101ca3447ab558bb7b4d1044c8a2f22b62`)

- Analytics now labels the field `Dato incluido más antiguo actualizado`, removing the unsupported source-delay claim. **Confirmed** in the deployed UI.
- Category editor exposes visible and accessible names for base nightly price and maximum occupancy. **Confirmed** with Playwright role/label locators; no category values were changed.
- The owner saved a fresh official USD quote after the additional MFA step; the PMS displayed `Cotización guardada: venta oficial a 1570 ARS por USD`. **Confirmed** from the visible app. No OTP is retained here.
- Tariff recommendation evaluation completed, but prepared no draft: `55 fechas sin sugerencia`, each because `no hay una temporada activa para esa fecha`. **Confirmed** for Doble Baño Compartido, 2026-11-06 through 2026-12-31. No tariff was published or changed.
- Suggestion: clarify in the recommendation UI that only dates in active seasons are evaluated, or evaluate the base/current tariff on non-season dates when the product rules permit. To test a positive recommendation path, seed a synthetic active season and at least three historical dates with verifiable USD conversion, then evaluate and discard the draft without publishing.

## Updated validation boundary

- Cloud UI evidence is from the owner profile at `https://app.hotels-pms.com` after the fixes were observed; separate manager and receptionist profile checks listed above remain from this run.
- `origin/main` points to `b76d07101ca3447ab558bb7b4d1044c8a2f22b62`.
- Full multi-persona regression is still incomplete: cleaner write permissions, positive recommendation generation/publication workflow, and several other operational modules/actions have not been covered in this pass. No third-party payment, message, OTA, or provider write was performed.

## Additional booking and cash checks (same deployed code)

- Reception created synthetic guest `QA Codex Round3 20261106 #42` and reservation `RES-QK6GHRH1` for Doble Baño Compartido, 2026-11-20 to 2026-11-22. The UI calculated ARS 120,000 from two nightly tariffs of ARS 60,000. The reception profile explicitly said it could not query USD conversion; it allowed saving in ARS. The reservation saved after a long wait. **Confirmed** in the visible UI.
- Reservation finance showed total ARS 120,000, received ARS 0, deposit ARS 60,000, and balance ARS 120,000. No payment transaction was recorded. **Confirmed**; the deposit amount appears to be the requested deposit, not collected cash.
- The USD cash view separated currencies and showed USD 0.00 confirmed for the selected business day, with an open USD cash session and USD 95.00 opening/expected balance. No cash movement was written. **Confirmed**.
- **Reliability finding:** the receptionist reservations page showed timeout errors for the operational action tray, movement groups, and recent-reservations panel while the table still showed records. The new reservation save also stayed in `Guardando la reserva…` for roughly 15 seconds before completing. A manager planilla showed a timeout notice while the occupancy grid remained visible. These were transient in this pass; retry/reload and backend timing correlation are needed before attributing a cause. **Confirmed UI symptoms; cause needs-verification.**
- Suggestion: add bounded request loading/error states that cannot remain stuck after the API eventually succeeds, and instrument the affected requests with request IDs and duration buckets. Retest under normal and slow-network conditions.

## Follow-up Playwright checks

- Repeated the reservation-page load in the receptionist profile after the timeout notices. The real-time status returned to connected, the action tray showed 4 open items, movement groups 1–4 loaded, and the reservation list showed 39 records. **Recovered after reload; intermittent issue remains confirmed, but no persistent failure reproduced.**
- Repeated the task-page load in the manager profile. It returned to connected, showed 0 open / 5 recorded tasks, and loaded recent handoffs. **Recovered after reload.**
- Created synthetic company `QA Codex Company Automated` with no personal contact data and agreed base rate ARS 50,000. The page saved it and showed five companies. **Confirmed.**
- Reception’s new-reservation form did not expose a company selector; owner’s create form did. The owner could select the synthetic company and the quote returned ARS 50,000 for one night, deposit ARS 15,000, and balance ARS 35,000. The company filter returned exactly the saved company reservation. **Corporate booking flow confirmed for owner.** The edit form intentionally disables company association after creation.
- Quote line source rendered as `Valor no reconocido` for the company rate. **UI label finding.** Suggestion: map the company-contract rate source to a named label such as “Tarifa acordada de empresa” in the quote breakdown.
- Created synthetic reservation `RES-BVA0Y9U8` (reception, ARS 60,000, no payment) and company reservation `RES-3LW7EQK3` (owner, ARS 50,000, no payment). Both appeared in the visible reservation list after saving. Save took about 19 seconds for each. **Confirmed UI result; latency cause not established.**
- The GitHub Actions concern was checked read-only: repository visibility is public, recent jobs use standard `ubuntu-latest`, GHCR packages are public, and the user billing usage summary reported Actions Linux and Actions storage at net amount 0 for October and November 2026. **No evidence that these pushes or image packages caused the attempted charge.** The actual billing notice/product remains unidentified; no workflow or billing setting was changed.

## Additional checks after the follow-up

- Stock: recorded a synthetic +1 ingress and −1 egress for `QA Codex Stock 20261105` in `QA móvil 1784864647210`. The visible stock returned to its prior 3.00 units, and both movements appeared in history. **Reversible stock movement confirmed.**
- Cash: switched the daily view between ARS and USD without recording a movement. ARS totals and the USD session remained separate; the USD daily summary showed US$ 0.00 while its session opening/expected balance was US$ 95.00. Restored the view to ARS. **Currency separation confirmed.**
- Laundry: owner view loaded the vendor, rate-backed period report, three linen types, two locations, remitos, and current vendor balance. Existing remitos displayed matching exit/return quantities; no discrepancy or shortfall was listed. The opening-count fields were available only for location/item cells without prior movement. No new laundry remito or linen movement was submitted.
- Manager tasks page recovered after reload with real-time status connected, 0 open and 5 recorded tasks. The create form exposed title, area, priority, optional room, due time, and handoff comment. No additional task was created in this follow-up.
- Company-rate label: reopened a fresh one-night quote for the synthetic company, then repeated after a full page reload. Both showed ARS 50,000, deposit ARS 15,000, balance ARS 35,000, 12 available rooms, and the USD estimate of US$ 32; the source still showed `Valor no reconocido`. The checked `origin/main` files already contain Spanish/English `company_base_price` labels and an E2E assertion, so no distinct source-code change was made for this symptom. **Cause needs verification against the deployed frontend build/source contract; the page did not expose its deployed SHA.** Suggestion: compare the served asset/deploy SHA with current main, then verify the quote `source` value if the current bundle is active. The reservation form was closed without saving.
- Access boundary: the three available signed-in profiles cover owner, manager, and receptionist. A separate cleaner account and master-admin account were not available in those profiles; the owner’s “Ver como” control explicitly says it does not change effective permissions. Those role-specific write paths remain unverified.

## Post-push smoke retest (`main` `4d5efb97`)

- Pushed the bounded read-timeout retry and accumulated QA evidence to `main`. After reloading the manager and receptionist profiles, both pages showed real-time connected; manager tasks showed 0 open / 5 recorded, while reception loaded 6 pending actions, movement groups 1–4, and all 41 reservation rows. No timeout reproduced in this smoke pass, so the new retry path itself was not observed firing.
- Reopened the company quote after a full page reload. Prices and balances still calculated correctly, but the source remained `Valor no reconocido`.
- **Confirmed cause in code:** company-base pricing replaces the pricing snapshot without nightly breakdown rows; `build_reservation_quote()` then creates fallback rows containing only date and price. The frontend substitutes the untranslated fallback `backend_quote`. Existing `company_base_price` translations do not fix this response. A backend correction and regression test are now in progress.
- The cloud page did not expose its deployed SHA. This smoke pass confirms the visible reservation/task data load, but not which post-push frontend build served the company quote.

## Company quote retest after backend source fix (`main` `5ecd256e`)

- The source-preservation fix and a pure unit regression test were pushed to `main`. The focused test passed (1/1); Ruff on touched files (ignoring two pre-existing `UP017` findings in the service) and `git diff --check` passed.
- After waiting, reloading the owner app, and preparing the same one-night company quote, the cloud still showed ARS 50,000, ARS 15,000 deposit, ARS 35,000 balance, and `Valor no reconocido`. I closed the unsaved form. **The app has not reflected the backend fix yet or its served backend source remains unverified.**
- Suggestion: use the normal release process to confirm the backend deployed SHA is `5ecd256e` (or a descendant), then repeat this quote. I did not open or change Render, Vercel, or Supabase.

## Final company quote cloud retest

- After the backend change propagated, the same unsaved one-night synthetic company quote displayed `Tarifa corporativa acordada` instead of `Valor no reconocido`, with ARS 50,000 total, ARS 15,000 deposit, and ARS 35,000 balance. **Cloud behavior now matches the code fix.** The page does not expose its deployed SHA. I closed the form without saving a reservation.

## Assignment and room-block checks

- Auto-assignment: recalculated proposal `#54`. Five future synthetic reservations remained in room 3; the run finished with no movements pending. **Proposal path loaded and completed; no room moved.**
- Reservation protection: toggled `RES-BVA0Y9U8` to “No permitir reasignar” and back to “Se puede reasignar”; both states were visible. **Reversible protection confirmed.**
- Manual assignment: moved `RES-BVA0Y9U8` from room 3 to compatible room 4, then restored it to room 3. The final fresh reservation list showed room 3. No payment was recorded.
- Date-based room block: prepared a one-night block for room 4 on 2026-12-06, previewed it (zero reservations to move), confirmed it, and resolved it. Active count changed 0 → 1 → 0; the UI stated the end date is exclusive and the room is free from 2026-12-07. **Block and resolution flows confirmed.**
- The room inventory separately showed room 2 with operational state `Bloqueada` while date-based active blocks were 0. This appears to be a distinct status from scheduled blocks. Suggestion: label both concepts clearly in the UI so operators can tell a current room status from a dated out-of-sale block.

## Follow-up cloud checks (frontend build SHA `74469847`; API SHA `577983d4` when checked)

- Analytics executive page initially showed a transient request-timeout alert while retaining the cached report and an older freshness timestamp. After reload and real-time reconnection, the alert cleared and the report rendered; the freshness field read `Dato incluido más antiguo actualizado el 3/11/26, 10:24 a. m.`. The operations analytics page loaded with the same freshness terminology and report data. **Transient timeout observed once; no repeat after reload.** Suggestion: keep the bounded retry and surface an explicit retry action only when both attempts fail; continue monitoring before attributing this to backend latency.
- Operations analytics listed synthetic reservation `RES-H2IOCNF5` (id 43) with status `checked_out` and outcome `Pendiente`. The reservations table confirms its planned stay is 2026-11-04 through 2026-11-07; nightly occupancy rows for 11/04–11/06 match that planned stay, so they do not establish occupancy beyond its planned checkout. **Outcome/status inconsistency confirmed in the visible UI; occupancy overcount not confirmed.** Suggestion: ensure the analytics summary outcome follows the terminal reservation status (`completed` on checkout), or clearly distinguish settlement disposition if `Pendiente` is intentionally about a separate decision.
- Manager housekeeping write path: changed room 10 from `Limpia` to `En limpieza`, observed the status update, restored it to `Limpia`, reloaded the page, and confirmed the persisted value remained `clean`. The manager page showed 1 dirty, 3 in progress, 35 clean, and 0 inspected rooms. **Reversible state transition and persistence confirmed; no net room-state change left behind.**
- Owner user-management page loaded available invitation roles and active hotel memberships. No invitation, alias, role, or membership action was submitted because the visible records belong to real accounts rather than synthetic QA identities.
- Room-state event creation, first attempt: the old owner form prefilled `started_at` with `2026-11-07T00:39:37.808Z`; its generic alert hid the expected future-time validation detail. **Resolved in frontend SHA `17aa0994`: start time is now blank and the API supplies its own current time; the UI surfaces 400 validation detail.** A later valid blank-start attempt exposed the separate API 500 documented below.
- Room-state history presentation: the old UI rendered raw `maintenance`, `deep_clean`, ISO UTC timestamps and creator/closer IDs (`5`). **Resolved in frontend SHA `17aa0994`: event/reason labels and dates are readable, and the page uses a neutral user label instead of raw IDs.** The fallback room text remains “No disponible”; a more explicit “Habitación no disponible” would read better.
- Waitlist date entry: the first automated attempt using Playwright `fill()` changed the native date input value without updating React state and the API rejected the incomplete date; repeating with keyboard/native date interaction created the synthetic waitlist entry successfully. The entry was then canceled and verified canceled, with no reservation created. **Automation artifact confirmed; not a product defect.** The proposal calculation timed out once and returned a valid suggestion after clicking retry; latency remains unproven.
- Build separation: after pushing `74469847`, `/build-meta.json` served frontend SHA `74469847ffa712c705881c94e47dd917a282e8a5`, while `https://api.hotels-pms.com/health` still reported backend SHA `577983d48833f08000d9ce8573ddbdfcdea91610`. The analytics outcome repair therefore had not reached the API when observed; it was not yet cloud-retested.
- Reception reservation list: the visible live list showed 11 check-outs today, while at least one reservation with planned departure today remained in `Pre check-in` and its row-level Check-out action was disabled. **Possible operational-count mismatch, needs verification**: the page may intentionally count scheduled departures regardless of check-in state, but the label “Check-outs hoy” can imply guests currently checked in. Suggestion: define the count as “salidas previstas” or exclude never-checked-in stays and expose them as overdue/pre-check-in departures. No reservation action was taken.
- Backend analytics fix cloud retest after push `e569755f`: `/health` reports API SHA `e569755f6821d9a9029ea975b48d0740f3f5d542`; the visible Operations table now renders `RES-H2IOCNF5` status `checked_out` with outcome `Completada`. **Backend fix verified in cloud.** The planned stay dates and nightly rows remain unchanged.
- Frontend release check after push through `17aa0994`: the first cache-busted read still returned `e569755f`, but a later cache-busted read served frontend SHA `17aa0994b14ffac4740545173e1e8f464ae5d45c`. The visible room-state events page then showed translated labels, localized timestamps, no raw user IDs, and an empty initial start time. **Frontend UI fix verified in cloud; deployment propagation took several minutes.** No Vercel dashboard was opened.
- Suggested-rate calculation: on the DBC category (2026-11-06 through 2026-12-31), the experimental evaluator completed but returned no suggestions for 55 dates, each reasoned as “no hay una temporada activa para esa fecha.” A second category also showed no configured seasons. **Calculation path completes and explains the missing input; no price was changed and no pending edit remained.** Suggestion: provide an active comparable season and enough confirmed historical dates with verifiable FX snapshots, and summarize the shared blocker once instead of repeating it for every date.
- Room-state event create retest on UI SHA `17aa0994` / API SHA `e569755f`: with room 10, maintenance/inspection, no note, and blank start time, the form showed “Guardando…” and then a generic error. Network response was HTTP 500 with safe body detail `Error interno del servidor`. Two controlled attempts returned the same failure; reloads confirmed no event persisted. **API create defect confirmed; fixed in commit `fb8be2bd` with a PostgreSQL 16 regression, then pushed with evidence in `0c177aee`.** Confirmed cause: aggregate query selected hotel timezone without aggregation, causing PostgreSQL `GroupingError` before commit.
- Cloud room-event retest after API deployed SHA `0c177aee85ff080cef7d4d28d8a74e75901f8db2`: created synthetic maintenance/inspection event #5 for room 10 with blank start time; UI showed it with server-supplied start time and a close action. Closed it successfully; reloaded view shows event #5 `Cerrado`, with start/end timestamps and neutral creator/closer labels. **Create, persistence, and close verified in cloud.** No active test event remains. Evidence: visible owner-profile page `https://app.hotels-pms.com/operacion/room-state-events` after reload.
- Remaining presentation suggestion: for historical events whose room or optional note is missing, replace the generic `No disponible` with a field-specific explanation such as “Habitación eliminada” or “Sin nota”. This is low priority and does not block create/close.

## Follow-up Playwright checks (`2026-11-07`, frontend `1413d7b0`, API `0c177aee`)

- Reception profile: quick availability query for Doble Baño Compartido, 2026-11-06 to 2026-11-07 returned `12 habitaciones disponibles`. Real-time banner briefly said reconnecting, then returned to “Conectado: cambios en tiempo real activos” within five seconds. **Query succeeded; no persistent realtime disconnect reproduced.**
- Guest page stale bundle: from both receptionist and manager profiles, navigating from a previously open app tab to `/huespedes` showed React Router's default error, `Failed to fetch dynamically imported module: .../GuestsPage-BmXVS8HG.js`. The old chunk URL responded with `text/html` containing `index.html` under `/assets/`, rather than JavaScript. A hard browser reload fetched current `index-hCCjZnlb.js` and `GuestsPage-CM4DoHNk.js`; the guest page then rendered and session/realtime returned. **Confirmed stale-runtime/chunk failure after deployment; hard reload recovers, but the visible error gives no recovery action.** Suggestion: detect failed dynamic imports and trigger a one-time safe reload or present a clear recovery screen; ensure repeated failures do not loop.
- Guest profile presentation: the QA guest detail page showed stay statuses `Pending`, `Checked Out`, and `Cancelled` while the UI language was Spanish. The alert selector defaulted to the consequential option `Prohibido alojar` even though the page said “Sin etiquetas activas.” No alert was added and no guest data saved. **Both UX issues confirmed.** Suggestion: localize stay statuses and use a neutral placeholder until the operator chooses a tag.
- Reservation allocation history: the Spanish reservations page showed recent trigger reasons `new_reservation` and `manual_api_recalculate` plus English backend note `Allocation run moved 1 reservation(s)`. **Localization gap confirmed.** Suggestion: map known trigger reasons and generated notes to localized labels while preserving unknown operational details safely.
- Manager auto-assignment page opened proposal #54. It showed five synthetic future reservations with no pending movements; room assignments remained room 3 and the page displayed “Esta propuesta ya no tiene movimientos pendientes.” **Proposal review page loaded; no new recalculation or room movement was submitted in this check.**
- Manager occupancy planilla loaded after its initial spinner; the 14-day grid showed Doble Baño Compartido availability dropping from 12 to 11 on 2026-11-20, matching a synthetic reservation starting that day. Sorting by category and moving 14 days forward then back to Hoy both worked. **Visible grid/navigation confirmed; no data changed.**
- Manager laundry page loaded one vendor, three linen types, two locations and prior movement counts after its initial loading state. Selecting Lavadero El Rápido exposed its rate section without changing rates. Existing movement cells with history were marked as having movements. **Read-only manager view confirmed.**
- Direct manager navigation to `/caja` showed “No tenés permiso para ver esta sección” and a link back to home. **Role boundary confirmed for cash access.** No cash or payment action was submitted.


## Fixes prepared from the 2026-11-07 follow-up audit

- Added a clear route recovery screen for stale lazy-loaded browser chunks, with a manual reload action and a notice that unsaved changes will be lost. Cloud behavior still needs retest after release.
- Localized known reservation allocation-history triggers and generated move notes while leaving operator-entered and unknown text intact. Cloud behavior still needs retest after release.
- Localized guest stay statuses and changed the guest alert selector to require an explicit choice instead of preselecting the consequential tag. Cloud behavior still needs retest after release.
- Changed the reservations metric to “Salidas previstas” / “Scheduled departures” and count only non-canceled, non-no-show stays departing today, including pre-check-in stays. Cloud behavior still needs retest after release.
- Replaced generic missing-value labels in room-event history with contextual room/note explanations. Cloud behavior still needs retest after release.
- Grouped the suggested-rate evaluator's missing-season blocker, added a link to season configuration, and kept rate calculation and saved prices unchanged. Cloud behavior still needs retest after release.
- Combined frontend validation: 168/168 unit tests, 5/5 i18n checks, lint, TypeScript, production build, and diff check passed. The build retains the existing large-chunk warning.


## Retest of `a94c1209` after cloud deployment

- `/build-meta.json` eventually reported frontend `code_sha=a94c1209a8aeb2aee80b348799acef54aef34e14`; no provider dashboard was opened.
- Suggested-rate evaluation in the owner profile completed. It showed `54 fechas omitidas: no hay temporadas activas que las cubran`, with a single guidance paragraph and the `Ir a temporadas` anchor link. The screen continued to show `Sin cambios pendientes`; no price or season was saved. One of the 55 dates had a different skip reason and was not part of the missing-season group.
- Room-event history in the owner profile now showed the historical missing room as `Habitación no disponible` and blank note as `Sin nota registrada`; the event with a room remained `Habitación: 10`.
- The reservation page showed `Salidas previstas: 1` for 2026-11-07. Recent allocation history rendered `Nueva reserva` and `Recalculo manual de asignaciones`, with the generated move note localized.
- Owner and a newly opened reception tab both showed stay statuses in Spanish (`Pendiente`, `Check-out`, `Cancelada`) and the neutral selected placeholder `Seleccioná una etiqueta` while the guest has no tags.
- **Stale tab remains reproducible:** the already-open receptionist tab still showed `Pending`, `Checked Out`, `Cancelled` and preselected `Prohibido alojar` even after invoking reload, while a new tab in that same signed-in profile rendered the corrected labels. This is being investigated; the cloud recovery fix is not yet verified for an already-open stale tab.
