"""
Utility to purge expired or consumed security tokens from the database.
"""
from app.adapters.memory_tokens import token_store


if __name__ == "__main__":
    cleaned = token_store.cleanup()
    print(f"Token store cleaned. Removed {cleaned} rows.")
