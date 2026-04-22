"""
Middleware to block mutating requests when subscription enforcement is enabled.
Not registered by default; enable with app.add_middleware(SubscriptionEnforcementMiddleware).
"""
from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import get_session_factory
from app.master_admin.billing_policy import evaluate_hotel_write_access
from app.services.subscription_entitlements import get_subscription_snapshot
from app.services.security import decode_access_token


class SubscriptionEnforcementMiddleware:
    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        request = Request(scope, receive=receive)
        if request.method in {"GET", "HEAD", "OPTIONS"}:
            await self.app(scope, receive, send)
            return

        settings = get_settings()
        enforcement_flag = getattr(settings, "SUBSCRIPTION_ENFORCEMENT", None)
        if enforcement_flag is None:
            enforcement_flag = getattr(settings, "SUBSCRIPTION_ENFORCEMENT_ENABLED", False)
        if not enforcement_flag:
            await self.app(scope, receive, send)
            return

        hotel_id_raw = request.headers.get("X-Hotel-Id") or request.query_params.get("hotel_id")
        try:
            hotel_id = int(hotel_id_raw) if hotel_id_raw else None
        except ValueError:
            hotel_id = None

        if not hotel_id:
            await self.app(scope, receive, send)
            return

        user_id = None
        auth_header = request.headers.get("Authorization") or ""
        if auth_header.lower().startswith("bearer "):
            token = auth_header.split(" ", 1)[1].strip()
            if token:
                try:
                    token_payload = decode_access_token(token)
                    raw_user_id = token_payload.get("sub") or token_payload.get("user_id")
                    if raw_user_id is not None:
                        user_id = int(str(raw_user_id))
                except Exception:
                    user_id = None

        SessionLocal = get_session_factory()
        db = SessionLocal()
        try:
            snapshot = get_subscription_snapshot(db, hotel_id)
            if snapshot.get("dirty"):
                db.commit()
            if user_id is not None:
                snapshot["user_id"] = user_id
            decision = evaluate_hotel_write_access(db, hotel_id, snapshot=snapshot)
            if decision.can_write:
                await self.app(scope, receive, send)
                return
            response = JSONResponse(
                status_code=402,
                content={
                    "detail": "SuscripciÃ³n en pausa o vencida",
                    "plan": snapshot.get("plan"),
                    "status": snapshot.get("status"),
                    "hotel_id": hotel_id,
                    "billing_reason": decision.reason,
                },
            )
            await response(scope, receive, send)
            return
        except Exception:
            db.rollback()
        finally:
            db.close()

        await self.app(scope, receive, send)
