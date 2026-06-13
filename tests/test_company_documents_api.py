from datetime import date

from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.database import Base, get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.main import app as fastapi_app
from app.models.company import Company
from app.models.guest import DocumentTypeEnum, Guest
from app.models.hotel_config import HotelConfiguration
from app.models.room import Room, RoomCategory, RoomStatusEnum
from app.models.user import User
from app.schemas.reservation import ReservationCreate
from app.services.reservation_service import create_reservation


def _override_auth(hotel_id: int, role: str, user_id: int = 10):
    def dependency():
        return AuthContext(
            hotel_id=hotel_id,
            user_id=user_id,
            user_email=f"{role}@test.com",
            user_role=role,
            is_verified=True,
            permissions=set(),
        )

    return dependency


def _client_with_db():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    Base.metadata.create_all(bind=engine)
    db = TestingSessionLocal()
    db.add_all(
        [
            HotelConfiguration(id=1, subscription_active=True),
            HotelConfiguration(id=2, subscription_active=True),
            User(id=10, email="user10@example.com", password_hash="test-hash", is_active=True, is_verified=True),
            User(id=55, email="user55@example.com", password_hash="test-hash", is_active=True, is_verified=True),
        ]
    )
    db.flush()

    def override_get_db():
        try:
            yield db
        finally:
            pass

    fastapi_app.dependency_overrides[get_db] = override_get_db
    client = TestClient(fastapi_app)
    return client, db, engine


def _seed_reservation(db, *, hotel_id: int = 1):
    category = RoomCategory(
        hotel_id=hotel_id,
        name=f"Standard {hotel_id}",
        code=f"STD{hotel_id}",
        base_price_per_night=100,
        max_occupancy=2,
    )
    db.add(category)
    db.flush()
    room = Room(hotel_id=hotel_id, room_number=f"{hotel_id}01", floor=1, category_id=category.id, status=RoomStatusEnum.AVAILABLE)
    guest = Guest(
        hotel_id=hotel_id,
        first_name="Ada",
        last_name="Lovelace",
        document_type=DocumentTypeEnum.DNI,
        document_number=f"{hotel_id}123",
        terms_accepted=True,
    )
    company = Company(
        hotel_id=hotel_id,
        legal_name=f"Acme {hotel_id} SA",
        display_name=f"Acme {hotel_id}",
        tax_id=f"30-{hotel_id}",
        requires_signature=True,
    )
    db.add_all([room, guest, company])
    db.flush()
    reservation = create_reservation(
        db,
        ReservationCreate(
            guest_id=guest.id,
            category_id=category.id,
            room_id=room.id,
            company_id=company.id,
            check_in_date=date(2026, 7, 1),
            check_out_date=date(2026, 7, 3),
        ),
        hotel_id=hotel_id,
    )
    db.flush()
    db.commit()
    db.refresh(company)
    db.refresh(reservation)
    return company, reservation


def test_company_documents_api_crud_and_status_flow():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "manager", user_id=55)
    try:
        company, reservation = _seed_reservation(db, hotel_id=1)

        created = client.post(
            "/api/company-documents",
            json={
                "reservation_id": reservation.id,
                "company_id": company.id,
                "doc_type": "signature_required",
                "file_name": "voucher.pdf",
                "file_url": "s3://docs/voucher.pdf",
                "requires_signature": True,
                "notes": "Need signature",
            },
        )
        assert created.status_code == 201
        body = created.json()
        assert body["status"] == "pending"
        assert body["hotel_id"] == 1

        listed = client.get(f"/api/company-documents/company/{company.id}")
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [body["id"]]

        signed = client.patch(f"/api/company-documents/{body['id']}/status", json={"status": "signed"})
        assert signed.status_code == 200
        assert signed.json()["status"] == "signed"
        assert signed.json()["signed_by_user_id"] == 55

        invalid = client.patch(f"/api/company-documents/{body['id']}/status", json={"status": "rejected"})
        assert invalid.status_code == 400
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_receptionist_cannot_manage_company_by_default():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "receptionist")
    try:
        company, reservation = _seed_reservation(db, hotel_id=1)

        company_response = client.post(
            "/api/companies",
            json={
                "legal_name": "Blocked SA",
                "display_name": "Blocked",
                "tax_id": "30-999",
            },
        )
        assert company_response.status_code == 403

        document_response = client.post(
            "/api/company-documents",
            json={
                "reservation_id": reservation.id,
                "company_id": company.id,
                "doc_type": "voucher_pdf",
                "file_name": "voucher.pdf",
            },
        )
        assert document_response.status_code == 403
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()


def test_company_documents_api_cross_hotel_isolation():
    client, db, engine = _client_with_db()
    fastapi_app.dependency_overrides[get_auth_context] = _override_auth(1, "owner")
    try:
        company_h1, reservation_h1 = _seed_reservation(db, hotel_id=1)
        company_h2, reservation_h2 = _seed_reservation(db, hotel_id=2)

        cross_create = client.post(
            "/api/company-documents",
            json={
                "reservation_id": reservation_h2.id,
                "company_id": company_h2.id,
                "doc_type": "voucher_pdf",
                "file_name": "foreign.pdf",
            },
        )
        assert cross_create.status_code == 400

        own_create = client.post(
            "/api/company-documents",
            json={
                "reservation_id": reservation_h1.id,
                "company_id": company_h1.id,
                "doc_type": "voucher_pdf",
                "file_name": "own.pdf",
            },
        )
        assert own_create.status_code == 201

        fastapi_app.dependency_overrides[get_auth_context] = _override_auth(2, "owner")
        hidden = client.get(f"/api/company-documents/company/{company_h1.id}")
        assert hidden.status_code == 200
        assert hidden.json() == []
    finally:
        fastapi_app.dependency_overrides.clear()
        db.close()
        engine.dispose()
