"""Atomic multi-room reservation creation and grouped balance summaries."""

from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.company import Company
from app.models.guest import Guest
from app.models.reservation import Reservation
from app.models.reservation_group import ReservationGroup
from app.schemas.reservation import ReservationCreate
from app.services.financial_ledger import billing_adjustment_totals_by_reservation, paid_amounts_by_reservation
from app.services.reservation_service import ReservationError, create_reservation


_SHARED_FIELDS = tuple(field for field in ReservationCreate.model_fields if field != "room_id")


def create_reservation_group(
    db: Session,
    *,
    hotel_id: int,
    reservations: list[ReservationCreate],
    actor_user_id: int | None,
    actor_role: str | None,
) -> tuple[ReservationGroup, list[Reservation]]:
    if not 2 <= len(reservations) <= 10:
        raise ReservationError("El grupo debe incluir entre 2 y 10 habitaciones.")
    first = reservations[0]
    if first.source.value != "direct":
        raise ReservationError("Los grupos solo se pueden crear para reservas directas.")
    if first.is_wait_listed:
        raise ReservationError("No se puede crear un grupo en lista de espera.")
    if first.total_amount is not None:
        raise ReservationError("Los grupos requieren una cotización vigente; no admiten tarifa manual.")
    if not first.quote_token:
        raise ReservationError("Cada habitación del grupo necesita una cotización vigente.")

    shared_values = first.model_dump(exclude={"room_id"})
    for reservation in reservations[1:]:
        if reservation.model_dump(exclude={"room_id"}) != shared_values:
            raise ReservationError(
                "Las habitaciones del grupo deben compartir huésped, empresa, fechas, ocupación, nota y tarifa."
            )
    requested_room_ids = [reservation.room_id for reservation in reservations]
    if any(room_id is None for room_id in requested_room_ids) and any(
        room_id is not None for room_id in requested_room_ids
    ):
        raise ReservationError("Asigná todas las habitaciones del grupo o dejá que el sistema las asigne.")
    explicit_room_ids = [room_id for room_id in requested_room_ids if room_id is not None]
    if len(explicit_room_ids) != len(set(explicit_room_ids)):
        raise ReservationError("Cada habitación del grupo debe ser distinta.")

    with db.begin_nested():
        group = ReservationGroup(
            hotel_id=hotel_id,
            guest_id=first.guest_id,
            company_id=first.company_id,
            check_in_date=first.check_in_date,
            check_out_date=first.check_out_date,
            notes=first.notes,
            created_by_user_id=actor_user_id,
        )
        db.add(group)
        db.flush()

        created = [
            create_reservation(
                db,
                reservation_data,
                hotel_id=hotel_id,
                actor_user_id=actor_user_id,
                actor_role=actor_role,
                group_id=group.id,
            )
            for reservation_data in reservations
        ]
        if any(reservation.room_id is None or reservation.is_wait_listed for reservation in created):
            raise ReservationError("No hay suficientes habitaciones disponibles para crear el grupo completo.")

    return group, created


def list_reservation_groups(
    db: Session,
    *,
    hotel_id: int,
    limit: int = 50,
    group_id: int | None = None,
) -> list[dict]:
    query = db.query(ReservationGroup).filter(ReservationGroup.hotel_id == hotel_id)
    if group_id is not None:
        query = query.filter(ReservationGroup.id == group_id)
    groups = query.order_by(ReservationGroup.created_at.desc(), ReservationGroup.id.desc()).limit(limit).all()
    if not groups:
        return []

    group_ids = [group.id for group in groups]
    reservation_rows = (
        db.query(
            Reservation.id,
            Reservation.group_id,
            Reservation.confirmation_code,
            Reservation.room_id,
            Reservation.total_amount,
            Reservation.amount_paid,
            Reservation.currency_code,
            Reservation.settlement_status,
            Reservation.status,
        )
        .filter(
            Reservation.hotel_id == hotel_id,
            Reservation.group_id.in_(group_ids),
            Reservation.deleted_at.is_(None),
        )
        .order_by(Reservation.group_id.asc(), Reservation.id.asc())
        .all()
    )
    reservation_ids = [row.id for row in reservation_rows]
    paid_by_reservation = paid_amounts_by_reservation(db, hotel_id, reservation_ids)
    adjustments_by_reservation = billing_adjustment_totals_by_reservation(db, hotel_id, reservation_ids)
    rows_by_group: dict[int, list] = {key: [] for key in group_ids}
    for row in reservation_rows:
        rows_by_group[row.group_id].append(row)

    guest_ids = {group.guest_id for group in groups}
    guests_by_id = {
        guest.id: guest
        for guest in db.query(Guest).filter(Guest.hotel_id == hotel_id, Guest.id.in_(guest_ids)).all()
    }
    company_ids = {group.company_id for group in groups if group.company_id is not None}
    companies_by_id = {
        company.id: company
        for company in db.query(Company).filter(Company.hotel_id == hotel_id, Company.id.in_(company_ids)).all()
    } if company_ids else {}

    result = []
    for group in groups:
        children = rows_by_group[group.id]
        total_amount = Decimal("0.00")
        amount_paid = Decimal("0.00")
        balance_due = Decimal("0.00")
        currencies = set()
        child_financials = []
        for child in children:
            company = companies_by_id.get(group.company_id)
            child_settlement_status = str(
                getattr(child.settlement_status, "value", child.settlement_status) or ""
            ).lower()
            child_is_deferred = bool(
                group.company_id is not None
                and (
                    bool(company and company.payment_deferred)
                    or child_settlement_status in {"deferred", "settled"}
                )
            )
            if not child_is_deferred:
                gross = Decimal(str(child.total_amount or 0))
                paid = paid_by_reservation.get(child.id, Decimal(str(child.amount_paid or 0)))
                adjustment = adjustments_by_reservation.get(child.id, Decimal("0.00"))
                total_amount += gross
                amount_paid += paid
                balance_due += max(Decimal("0.00"), gross + adjustment - paid)
                child_financials.append(
                    {
                        "id": child.id,
                        "confirmation_code": child.confirmation_code,
                        "total_amount": gross.quantize(Decimal("0.01")),
                        "amount_paid": paid.quantize(Decimal("0.01")),
                        "balance_due": max(Decimal("0.00"), gross + adjustment - paid).quantize(Decimal("0.01")),
                        "currency_code": child.currency_code,
                        "status": str(getattr(child.status, "value", child.status)),
                        "company_billing_deferred": False,
                    }
                )
            else:
                child_financials.append(
                    {
                        "id": child.id,
                        "confirmation_code": child.confirmation_code,
                        "total_amount": None,
                        "amount_paid": None,
                        "balance_due": None,
                        "currency_code": child.currency_code,
                        "status": str(getattr(child.status, "value", child.status)),
                        "company_billing_deferred": True,
                    }
                )
            currencies.add(child.currency_code)
        guest = guests_by_id.get(group.guest_id)
        company = companies_by_id.get(group.company_id)
        company_billing_deferred = bool(
            group.company_id is not None
            and (
                bool(company and company.payment_deferred)
                or any(
                    str(getattr(row.settlement_status, "value", row.settlement_status) or "").lower()
                    in {"deferred", "settled"}
                    for row in children
                )
            )
        )
        result.append(
            {
                "id": group.id,
                "hotel_id": group.hotel_id,
                "guest_id": group.guest_id,
                "guest_name": f"{guest.first_name} {guest.last_name}".strip() if guest else "",
                "company_id": group.company_id,
                "company_name": company.display_name if company else None,
                "check_in_date": group.check_in_date,
                "check_out_date": group.check_out_date,
                "notes": group.notes,
                "reservation_count": len(children),
                "room_count": sum(1 for row in children if row.room_id is not None),
                "reservation_ids": [row.id for row in children],
                "reservation_codes": [row.confirmation_code for row in children],
                "reservations": child_financials,
                "total_amount": None if company_billing_deferred else total_amount.quantize(Decimal("0.01")),
                "amount_paid": None if company_billing_deferred else amount_paid.quantize(Decimal("0.01")),
                "balance_due": None if company_billing_deferred else balance_due.quantize(Decimal("0.01")),
                "company_billing_deferred": company_billing_deferred,
                "currency_code": next(iter(currencies)) if len(currencies) == 1 else "ARS",
                "created_at": group.created_at,
            }
        )
    return result
