"""
Developer reset helper: drops dev.db and recreates tables.
Usage: python -m app.scripts.dev_reset
"""
from app.database import init_db, Base
import app.models  # noqa: F401


def reset(db_url: str | None = None):
    # Recreate database
    engine = init_db(db_url)
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    print("Database reset complete")


if __name__ == "__main__":
    reset()
