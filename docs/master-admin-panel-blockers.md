# Master Admin Panel Blockers

Date: 2026-04-21

## Current status

The owner master panel implementation is functionally in place and the targeted backend regression suite passes.

## Blockers preventing full repo-wide validation

- `frontend` global lint is still failing on pre-existing issues outside the master admin scope.
- The failures currently reported by `npm run lint` are in:
  - `frontend/src/views/protected/ReservationsPage.tsx`
  - `frontend/src/views/protected/SettingsHotelPage.tsx`
  - `frontend/src/views/protected/SettingsUsersPage.tsx`
  - `frontend/src/views/public/ForgotPasswordPage.tsx`
- Additional warnings are also present in existing files such as:
  - `frontend/src/components/CheckoutStub.tsx`
  - `frontend/src/hooks/useIntegrations.ts`
  - `frontend/src/views/onboarding/OnboardingWizard.tsx`
  - `frontend/src/views/protected/DashboardPage.tsx`
  - `frontend/src/views/protected/RoomsPage.tsx`
  - `frontend/src/views/protected/SettingsConnectionsPage.tsx`
  - `frontend/src/views/public/PricingPage.tsx`

## Resulting decision

Do not merge to `next` or `main` until the repo-wide frontend lint baseline is cleared or the pre-existing failures are handled in a separate scoped task.

