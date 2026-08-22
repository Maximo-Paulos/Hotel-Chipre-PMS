"""notification_outbox/daily_report_schedules are FORCE ROW LEVEL SECURITY
tenant tables with no master-admin bypass (alembic/versions/20260818_
notifications.py): a query with no app.hotel_id set returns zero rows on
Postgres. The Celery task wrappers must loop per active hotel and set that
context before calling the (hotel-agnostic) service functions -- this test
pins that multi-hotel loop actually fans out and aggregates, not just that a
single hotel happens to work."""
from __future__ import annotations

from sqlalchemy.orm import Session, sessionmaker

from app.models.hotel_config import HotelConfiguration
from app.models.hotel_membership import HotelMembership
from app.models.notification import Notification, NotificationChannelEnum, NotificationOutbox, NotificationOutboxStatusEnum
from app.models.user import User
from app.tasks import notification_tasks


def _hotel_with_pending_in_app_notification(db: Session, hotel_id: int, user_id: int) -> None:
    db.add(HotelConfiguration(id=hotel_id, subscription_active=True))
    db.add(User(id=user_id, email=f"user{user_id}@example.test", password_hash="x", is_verified=True))
    db.flush()
    db.add(HotelMembership(hotel_id=hotel_id, user_id=user_id, role="owner", status="active"))
    db.flush()
    db.add(
        NotificationOutbox(
            hotel_id=hotel_id,
            event_type="reservation.created",
            dedupe_key=f"reservation:{hotel_id}:created",
            channel=NotificationChannelEnum.IN_APP,
            recipient_user_id=user_id,
            title="New reservation",
            status=NotificationOutboxStatusEnum.PENDING,
        )
    )


def test_process_outbox_delivers_across_every_active_hotel(db: Session, db_engine, monkeypatch):
    _hotel_with_pending_in_app_notification(db, hotel_id=1, user_id=10)
    _hotel_with_pending_in_app_notification(db, hotel_id=2, user_id=20)
    db.commit()

    # notification_tasks._session() normally opens its own engine from
    # settings.DATABASE_URL; point it at this test's in-memory engine instead.
    monkeypatch.setattr(notification_tasks, "_session", lambda database_url=None: sessionmaker(bind=db_engine)())

    totals = notification_tasks.process_outbox()

    assert totals["sent"] == 2
    delivered_hotels = {row.hotel_id for row in db.query(Notification).all()}
    assert delivered_hotels == {1, 2}
