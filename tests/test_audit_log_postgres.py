from sqlalchemy import func
from sqlalchemy.orm import sessionmaker

from app.models.audit_log import AuditActionEnum, AuditLog
from app.models.hotel_config import HotelConfiguration
from app.services.audit_log_service import create_audit_log


def test_postgres_audit_writer_does_not_commit_the_business_transaction(pg_engine):
    session_factory = sessionmaker(bind=pg_engine, autocommit=False, autoflush=False)
    with session_factory() as db:
        hotel_id = (db.query(func.coalesce(func.max(HotelConfiguration.id), 0)).scalar() or 0) + 1
        db.add(HotelConfiguration(id=hotel_id, hotel_name="Audit transaction regression"))
        db.flush()
        create_audit_log(
            db,
            hotel_id=hotel_id,
            table_name="hotel_configuration",
            record_id=hotel_id,
            action=AuditActionEnum.CREATE,
        )
        db.rollback()

    with session_factory() as verify:
        assert verify.get(HotelConfiguration, hotel_id) is None
        assert verify.query(AuditLog).filter_by(hotel_id=hotel_id).count() == 0
