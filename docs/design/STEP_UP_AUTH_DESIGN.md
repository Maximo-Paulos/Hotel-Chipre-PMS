# Step-up verification token — design (not implemented)

Status: **design only, nothing wired to a live endpoint.** The owner asked
for two things for a *future* loop: (1) confirm the permission matrix
already gates individual operational actions instead of hiding several
behind one generic code, and (2) design — on paper — an OTP-style override
so an employee without a permission can still perform the action if the
owner hands them a one-time code, "como el token del banco". This document
covers both. No migration, model, or endpoint in this document has been
created in code.

## Part 1 — Audit: is the matrix already action-granular?

`app/services/permission_service.py` defines 20 permission codes today:

| Code | Covers |
|---|---|
| `config:manage` | Hotel configuration |
| `permissions:manage` | Editing the permission matrix itself |
| `guest:edit` | Editing guest records |
| `guest:tags` | Guest tags |
| `guest:export` | Exporting guest data |
| `reservation:create` | Creating a reservation |
| `reservation:charge` | Adding a charge/payment to a reservation |
| `reservation:room_move` | Moving a reservation to another room |
| `reservation:manual_rate` | Setting a manual total on a reservation |
| `checkin:perform` | Check-in, partial check-in, and check-out (`app/api/checkin.py`) |
| `checkin:override_prohibido` | Overriding a "prohibido alojar" guest flag |
| `room_block:create` | Creating a room block |
| `room_block:release` | Releasing a room block |
| `company:manage` | Managing companies |
| `cash:operate` | Cash register operations |
| `cash:approve_difference` | Approving a cash difference |
| `stock:operate` | Stock movements |
| `stock:adjust` | Authorizing stock adjustments |
| `reports:view` | Viewing reports |
| `apikey:manage` | API key management |
| `laundry:manage_vendors` / `laundry:operate_remitos` | Laundry vendor admin / remito operations |

These 20 are already one-code-per-action — none of them bundle two
distinct operations behind a single flag (the `room_block:create` /
`room_block:release` split fixed in this same session, see the
`fix(security)` commit, is exactly this granularity working as intended
after the bug fix).

**Gap found: two real actions the owner explicitly named have no
permission code at all yet** — they're gated by `require_roles(...)`
instead, which is a coarse "one of these roles" allow-list, not a
matrix entry an owner can toggle per role from Settings → Permisos:

- **Cancel reservation** — `POST /api/reservations/{id}/cancel`
  (`app/api/reservations.py:501-506`), gated by
  `require_roles("owner", "co_owner", "manager")`.
- **Mark no-show** — `POST /api/reservations/{id}/noshow`
  (`app/api/reservations.py:638-639`), same pattern.

Interesting detail found while auditing `cancel_reservation`: it already
accepts a `manager_pin: str | None` query parameter
(`app/api/reservations.py:504`) that is **never read or validated anywhere
in the function body** — dead parameter, not a real PIN check. It's a
signpost that this exact need (a secondary code to unlock a restricted
action) was anticipated before, just never finished. Worth keeping in mind
as prior art, not touching today.

Per the C5 decision already made this session (`docs/design/RBAC_DESIGN.md`
context, and the plan's "no migrar los 177 `require_roles`" rule): only
migrate a `require_roles` site to `require_permission` when the owner
actually wants that specific action delegable per-role. Cancel and no-show
are both explicitly named in the owner's request, so they're the two
concrete candidates for a future `reservation:cancel` /
`reservation:no_show` permission code — not done today, flagged for the
loop that activates per-role toggles.

**Audit conclusion:** the base is 90% ready. Adding the two missing codes
(`reservation:cancel`, `reservation:no_show`) to `PERMISSION_DEFINITIONS`
and `DEFAULT_MATRIX`, and swapping their `require_roles(...)` for
`require_permission(...)`, is the only gap — a small, mechanical follow-up,
not a redesign.

## Part 2 — Step-up token design

### The shape of the problem

`require_permission(code)` (`app/dependencies/auth.py:153`) currently has
exactly one outcome when `resolve()` returns `False`: `403`. The ask is a
second path — a role without standing permission can still pass if the
request also carries a short-lived code the owner generated for that
specific employee, action, and moment.

### Reuse, don't invent

The codebase already has a working OTP pattern for exactly this shape of
problem — 6-digit time-limited codes for email verification and password
reset, rate-limited via `SimpleRateLimiter` (`app/adapters/rate_limiter.py`).
The step-up token reuses that pattern instead of inventing a new one:

- A new `code_guess_limiter`-style limiter throttles *redemption* attempts
  (guessing the code), separate from how often the owner can *issue* one.
- Storage follows the same shape as `RateLimitEvent` / `SecurityAuditLog`:
  hotel-scoped, no exotic table.

### Data model (proposed — not created)

```python
class PermissionOverrideToken(Base):
    __tablename__ = "permission_override_tokens"

    id = Column(Integer, primary_key=True)
    hotel_id = Column(Integer, ForeignKey("hotel_configuration.id", ondelete="CASCADE"), nullable=False)
    permission_code = Column(String(64), nullable=False)       # e.g. "reservation:cancel"
    issued_by_user_id = Column(Integer, nullable=False)         # owner/co_owner only, enforced at issue time
    issued_to_user_id = Column(Integer, nullable=True)          # optional: pin to one employee, null = any holder
    code_hash = Column(String(128), nullable=False)              # sha256, never store the raw code
    expires_at = Column(DateTime, nullable=False)                # short TTL, e.g. 10 minutes
    redeemed_at = Column(DateTime, nullable=True)                # single-use: set on first successful redemption
    redeemed_by_user_id = Column(Integer, nullable=True)
    created_at = Column(DateTime, nullable=False, default=...)

    __table_args__ = (
        Index("ix_permission_override_tokens_hotel_code", "hotel_id", "permission_code"),
    )
```

Hashed at rest (same principle as password/reset-code storage elsewhere in
`app/services/auth_service.py`) — a DB read never exposes a redeemable
code. Scoped to `(hotel_id, permission_code)`, optionally pinned to one
employee, single-use, short TTL. No standing "unlock everything" token —
one code unlocks one action, once.

### Issue flow (owner-facing, future UI)

1. Owner/co-owner (only — enforced same as `permissions:manage` today) picks
   an employee and an action from a screen listing the permission codes the
   employee currently lacks.
2. Backend generates a random 6-8 digit code, stores its hash + a short
   expiry (e.g. 10 min), returns the **plaintext code once** in the response
   — never persisted in plaintext, never retrievable again.
3. Owner reads/hands the code to the employee verbally or via the device
   already in front of them (no SMS/email infra needed for v1 — the owner
   is standing there, same as the manager_pin's original intent).

### Redemption flow (employee-facing)

1. Employee attempts the restricted action (e.g. cancel a reservation) and
   the UI shows a 403 with an inline "tengo un código" field instead of a
   dead end.
2. Frontend resends the same request with an extra header, e.g.
   `X-Permission-Override-Code: 482913`.
3. `require_permission()` gains one extra step, inserted right before the
   existing `403` raise in `app/dependencies/auth.py:171`:

```python
if not resolve(db, context.hotel_id, context.user_role, permission):
    override_code = request.headers.get("X-Permission-Override-Code")
    if override_code and redeem_override_token(
        db, hotel_id=context.hotel_id, permission_code=permission,
        user_id=context.user_id, code=override_code,
    ):
        audit_permission_override_used(db, hotel_id=context.hotel_id,
                                        user_id=context.user_id, permission_code=permission)
        return context  # allowed via override, not standing permission
    audit_permission_denied(...)  # existing behavior, unchanged
    raise HTTPException(403, ...)
```

`redeem_override_token()` is the only new function on the hot path: look up
by `(hotel_id, permission_code)`, check `redeemed_at is None` and
`expires_at > now`, compare `sha256(code)` to `code_hash`, and if it
matches, set `redeemed_at`/`redeemed_by_user_id` in the same transaction
(so a race between two simultaneous redemptions can only succeed once —
whichever request's `UPDATE ... WHERE redeemed_at IS NULL` commits first).
Failed attempts go through `code_guess_limiter` exactly like the existing
password-reset code guesses, so the 6-8 digit space can't be brute-forced
within the token's TTL.

### Audit trail

Every override redemption writes a `SecurityAuditLog` row
(`app/models/security_audit_log.py`) with
`action="permission.override.redeemed"`, `resource_type=permission_code`,
and `details` carrying who issued it and who redeemed it — the owner
already reviews this table for `permission.denied` events, so an override
use shows up in the same place, not a separate feed. This is what makes
the mechanism auditable rather than a silent bypass: every action taken
under an override is traceable to the specific owner who issued the code
and the specific employee who redeemed it.

### Why this shape and not something else

- **No new infra.** Reuses `SimpleRateLimiter`, `SecurityAuditLog`, and the
  hash-at-rest convention already used for reset codes — no SMS gateway, no
  external OTP service, no new dependency.
- **Single insertion point.** The only production code path that changes is
  the one `if` branch inside `require_permission()` — every one of the (now
  20, soon 22) call sites gets the override capability for free, with zero
  per-endpoint wiring.
- **Scoped, not a master key.** A code unlocks one action, once, within
  minutes — not "admin mode" for the rest of the shift. If an employee
  needs to cancel three reservations, that's three codes, which is a
  feature: it keeps the owner in the loop per use, matching "como el token
  del banco" (a bank OTP authorizes one transaction, not a session).

### What is explicitly deferred to the activation loop

- The `PermissionOverrideToken` model + Alembic migration.
- The issue endpoint (`POST /api/permissions/override-tokens`) and its
  owner-only UI.
- The `redeem_override_token()` service function and the `require_permission()` edit above.
- The frontend's 403 → "tengo un código" inline retry flow.
- The two missing permission codes from Part 1 (`reservation:cancel`,
  `reservation:no_show`) and swapping their `require_roles` for
  `require_permission`.

None of this is connected to a live endpoint today, per the owner's
explicit instruction that today's scope is audit + design only.
