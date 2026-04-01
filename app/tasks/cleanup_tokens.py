"""
Utility to purge expired codes from the in-memory token store.
Intended for dev; in production move tokens to Redis with TTL.
"""
from app.adapters.memory_tokens import token_store


def cleanup():
    token_store.cleanup()


if __name__ == "__main__":
    cleanup()
    print("Token store cleaned.")
