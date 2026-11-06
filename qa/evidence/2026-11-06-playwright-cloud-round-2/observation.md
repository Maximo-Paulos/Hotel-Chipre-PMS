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
