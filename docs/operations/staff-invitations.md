# Onboarding and staff invitations

The onboarding Staff step accepts **Copropietaria**, **Gerencia**, **Recepción**, and **Limpieza**. It never accepts a Dueño invitation. Only the hotel owner can assign the Copropietaria role; co-owners may invite the other staff roles. Staff rows can be removed, and each row has a stable client key while it is edited.

Adding an email creates a pending invitation and attempts delivery after the invitation transaction commits. The onboarding response reports delivery as `sent`, `failed`, or `not_configured`; it does not return invitation tokens. Email content uses the Spanish role name, a one-time acceptance link, and the fixed `/login` address for later visits.

Owners and co-owners with user-management permission can view pending invitations under **Configuración → Usuarios**. The list is scoped to the active hotel and never exposes tokens or token hashes. Reenviar rotates the one-time link; older links stop working. The new link can be copied from the invitation result card. Cancel changes the invitation and invited membership to revoked. An owner can also cancel a legacy pending Dueño invitation; after cancellation, that account can be invited with an ordinary staff role.

Previewing an accepted, revoked, expired, or unknown link returns a stable `INVITATION_*` code and the UI offers a clean path to `/login` or the current user's role landing page. Failed validation attempts do not consume the successful-invitation quota. The quota is 20 successful invitation creations or resends per user per hour.

Focused regression coverage:

- `tests/test_staff_invitation_service.py`
- `tests/test_onboarding_staff_roles.py`
- `tests/test_invitation_management_api.py`
- `tests/test_invitations.py`
- `tests/test_rate_limiting.py`
- `frontend/e2e/google-invitation-access.spec.ts`
- `frontend/e2e/reused-invitation-link.spec.ts`
- `frontend/e2e/auth-onboarding-journey.spec.ts`
