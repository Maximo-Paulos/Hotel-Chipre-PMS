from concurrent.futures import ThreadPoolExecutor
from threading import Barrier
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.adapters import memory_tokens
from app.database import Base
from app.models.security_token import SecurityToken


def test_concurrent_consumption_allows_only_one_verification(tmp_path):
    engine = create_engine(
        f"sqlite:///{(tmp_path / 'token-race.sqlite').as_posix()}",
        connect_args={"check_same_thread": False, "timeout": 30},
    )
    Base.metadata.create_all(bind=engine, tables=[SecurityToken.__table__])
    SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
    token_store = memory_tokens.TokenStore()

    try:
        with SessionLocal() as session:
            token_store.issue(session, "password_reset", "race@example.com", "123456")
            session.commit()

        both_tokens_read = Barrier(2)
        original_verify_password = memory_tokens.verify_password

        def verify_after_both_reads(password, password_hash):
            both_tokens_read.wait(timeout=10)
            return original_verify_password(password, password_hash)

        def consume_token():
            with SessionLocal() as session:
                result = token_store.verify(
                    session,
                    "password_reset",
                    "race@example.com",
                    "123456",
                    consume=True,
                )
                session.commit()
                return result

        with patch.object(memory_tokens, "verify_password", verify_after_both_reads):
            with ThreadPoolExecutor(max_workers=2) as executor:
                results = list(executor.map(lambda _unused: consume_token(), range(2)))

        assert sorted(results) == [False, True]

        with SessionLocal() as session:
            consumed_tokens = (
                session.query(SecurityToken)
                .filter(SecurityToken.consumed_at.is_not(None))
                .all()
            )
            assert len(consumed_tokens) == 1
    finally:
        Base.metadata.drop_all(bind=engine, tables=[SecurityToken.__table__])
        engine.dispose()
