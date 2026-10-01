"""PostgreSQL row-lock helpers for ORM queries with eager relationships."""

from sqlalchemy.orm import Query


def lock_query(query: Query, model: type) -> Query:
    """Lock only rows from ``model`` even when the query joins relationships.

    PostgreSQL rejects an unqualified ``FOR UPDATE`` on the nullable side of
    an outer join. Explicitly targeting the domain row keeps eager loading
    intact while preserving the intended transaction lock.
    """
    return query.with_for_update(of=model)
