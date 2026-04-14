"""
Middleware to block mutating requests when subscription enforcement is enabled.
Not registered by default; enable with app.add_middleware(SubscriptionEnforcementMiddleware).
"""
from fastapi import Request
from fastapi.responses import JSONResponse

from app.config import get_settings
from app.database import get_session_factory
from app.services.subscription_entitlements import get_subscription_snapshot


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

        SessionLocal = get_session_factory()
        db = SessionLocal()
        try:
            snapshot = get_subscription_snapshot(db, hotel_id)
            if snapshot.get("dirty"):
                db.commit()
            if not snapshot.get("can_write", True):
                response = JSONResponse(
                    status_code=402,
                    content={
                        "detail": "Suscripción en pausa o vencida",
                        "plan": snapshot.get("plan"),
                        "status": snapshot.get("status"),
                        "hotel_id": hotel_id,
                    },
                )
                await response(scope, receive, send)
                return
        except Exception:
            db.rollback()
        finally:
            db.close()

        await self.app(scope, receive, send)
