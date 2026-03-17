import sys, os
sys.path.append(os.getcwd())
from app.database import init_db, get_session_factory, Base
from app.models.room import Room, RoomCategory
from app.models.guest import Guest, GuestCompanion
from app.models.reservation import Reservation
from app.models.transaction import Transaction
from app.models.hotel_config import HotelConfiguration
engine = init_db()
Base.metadata.drop_all(bind=engine)
Base.metadata.create_all(bind=engine)
from app.main import seed_database
factory = get_session_factory()
db = factory()
try:
    print(seed_database(db))
    db.commit()
finally:
    db.close()
