from __future__ import annotations

from tests.smoke.helpers import register_owner, seed_operational_reservation
from app.models.reservation import ReservationStatusEnum
from app.dependencies.auth import AuthContext, get_auth_context
import app.main as main_module


def _receptionist_context(hotel_id: int):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=997,
            user_email="receptionist-smoke@example.com",
            user_role="receptionist",
            is_verified=True,
        )

    return dependency


def test_receptionist_can_view_operations_summary_and_pending_actions(client, engine):
    """GET /api/reservations/{id}/operations-summary and
    GET /api/reservations/actions/pending were owner/co_owner/manager/
    housekeeping only, omitting receptionist.

    operations-summary feeds the "Ficha" modal on the Reservations page
    (Operaciones de estadía + Consumos y cargos): receptionist could add a
    charge (reservation:charge) but then never see it, or the updated
    operational balance, because the query kept 403ing.

    actions/pending feeds the "Acciones pendientes" widget, and its hook
    defaults to `data ?? []` on error, so receptionist silently saw "0
    abiertas / No hay acciones operativas pendientes" instead of an error --
    hiding real manual-review/OTA-reconciliation follow-ups from front desk.
    """
    headers, hotel_id = register_owner(client, "reservation-ops-owner-summary@example.com")
    seeded = seed_operational_reservation(
        engine,
        hotel_id,
        reservation_status=ReservationStatusEnum.FULLY_PAID,
        total_amount=150.0,
        amount_paid=150.0,
        requires_manual_review=True,
    )

    main_module.app.dependency_overrides[get_auth_context] = _receptionist_context(hotel_id)
    try:
        summary = client.get(f"/api/reservations/{seeded['reservation_id']}/operations-summary")
        assert summary.status_code == 200, summary.text

        pending = client.get("/api/reservations/actions/pending")
        assert pending.status_code == 200, pending.text
    finally:
        del main_module.app.dependency_overrides[get_auth_context]
