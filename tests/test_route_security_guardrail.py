from __future__ import annotations

import fnmatch
import inspect
from dataclasses import dataclass

from fastapi.routing import APIRoute, iter_route_contexts

from app.main import app


AUTH_DEPENDENCY_NAMES = {
    "get_auth_context",
    "require_permission",
    "require_roles",
    "require_platform_admin",
    "get_public_api_context",
}

WEBHOOK_SIGNATURE_FUNCTION_NAMES = {
    "validate_mercadopago_webhook_signature",
    "verify_stripe_signature",
}


@dataclass(frozen=True)
class PublicRoute:
    pattern: str
    reason: str


PUBLIC_ALLOWLIST = (
    PublicRoute("/", "SPA shell is public; it serves static frontend HTML only."),
    PublicRoute("/{full_path:path}", "SPA fallback is public; API/assets/docs paths are rejected in the handler."),
    PublicRoute("/health", "Liveness probe; no sensitive tenant data."),
    PublicRoute("/health/*", "Health probes for operations and infrastructure monitoring."),
    PublicRoute("/docs", "OpenAPI UI; schema metadata only, no tenant data."),
    PublicRoute("/openapi.json", "OpenAPI schema; no tenant data."),
    PublicRoute("/redoc", "OpenAPI UI; schema metadata only, no tenant data."),
    PublicRoute("/api/auth/*", "Authentication bootstrap flows are unauthenticated by design."),
    PublicRoute("/api/invitations/*", "Invitation accept/preview is protected by signed invitation tokens."),
    PublicRoute("/api/integrations/oauth/*/callback", "OAuth provider callback is protected by signed OAuth state."),
    PublicRoute("/api/webhooks/booking/*", "OTA machine webhook; scoped by hotel id and stored webhook secret."),
    PublicRoute("/api/webhooks/expedia/*", "OTA machine webhook; scoped by hotel id and stored webhook secret."),
    PublicRoute("/api/webhooks/despegar/*", "OTA machine webhook; scoped by hotel id and stored webhook secret."),
    PublicRoute("/api/webhooks/booking", "Deprecated OTA webhook always returns 410 Gone."),
    PublicRoute("/api/webhooks/expedia", "Deprecated OTA webhook always returns 410 Gone."),
    PublicRoute("/api/webhooks/despegar", "Deprecated OTA webhook always returns 410 Gone."),
    PublicRoute("/api/payment-link-tests/mercadopago/webhook", "MercadoPago machine webhook verifies x-signature."),
    PublicRoute("/api/payment-links/mercadopago/webhook", "MercadoPago machine webhook verifies x-signature."),
    PublicRoute("/payment-links/mercadopago/webhook", "MercadoPago machine webhook verifies x-signature."),
    PublicRoute("/api/master-admin/auth/login", "Master-admin login is the unauthenticated session bootstrap."),
    PublicRoute("/api/master-admin/email/oauth/gmail/callback", "Retired external OAuth callback always returns 410 Gone."),
    PublicRoute("/api/master-admin/stripe/webhook", "Stripe machine webhook verifies Stripe-Signature."),
    PublicRoute("/api/seed", "Demo utility; handler is gated by TESTING/DEMO_MODE."),
    PublicRoute("/api/reset", "Demo utility; handler is gated by TESTING/DEMO_MODE."),
    PublicRoute("/api/connections/*", "Retired legacy connection API always returns 410 Gone in main app."),
    PublicRoute("/api/email", "Retired legacy email API always returns 410 Gone."),
    PublicRoute("/api/email/*", "Retired legacy email API always returns 410 Gone."),
    PublicRoute("/api/reference/timezones", "Public reference catalog used before hotel onboarding/auth."),
)


def _dependency_call_name(call) -> str:
    return getattr(call, "__name__", "") or ""


def _dependency_call_qualname(call) -> str:
    return getattr(call, "__qualname__", "") or ""


def _walk_dependants(dependant, seen: set[int] | None = None):
    if seen is None:
        seen = set()
    if id(dependant) in seen:
        return
    seen.add(id(dependant))
    yield dependant
    for child in getattr(dependant, "dependencies", ()) or ():
        yield from _walk_dependants(child, seen)


def _route_has_auth_dependency(route: APIRoute) -> bool:
    for dependant in _walk_dependants(route.dependant):
        call = getattr(dependant, "call", None)
        name = _dependency_call_name(call)
        qualname = _dependency_call_qualname(call)
        if name in AUTH_DEPENDENCY_NAMES:
            return True
        if qualname.startswith("require_platform_admin."):
            return True
        if qualname.startswith("require_public_api_purpose."):
            return True
    return False


def _path_is_allowlisted(path: str) -> bool:
    return any(fnmatch.fnmatchcase(path, item.pattern) for item in PUBLIC_ALLOWLIST)


def _endpoint_source_mentions(endpoint, function_names: set[str]) -> bool:
    try:
        source = inspect.getsource(endpoint)
    except (OSError, TypeError):
        return False
    return any(f"{function_name}(" in source for function_name in function_names)


def _route_has_webhook_signature_gate(route: APIRoute) -> bool:
    return _endpoint_source_mentions(route.endpoint, WEBHOOK_SIGNATURE_FUNCTION_NAMES)


def _route_has_master_admin_session_gate(route: APIRoute) -> bool:
    return route.path.startswith("/api/master-admin/") and _endpoint_source_mentions(
        route.endpoint,
        {"require_master_admin"},
    )


def _is_route_secured(route: APIRoute) -> bool:
    return (
        _route_has_auth_dependency(route)
        or _route_has_webhook_signature_gate(route)
        or _route_has_master_admin_session_gate(route)
    )


def test_all_routes_are_authenticated_or_explicitly_allowlisted():
    # ponytail: FastAPI >=0.137 wraps included sub-routers in `_IncludedRouter`
    # objects, so `app.routes` is no longer a flat list of `APIRoute` -- a naive
    # `isinstance(route, APIRoute)` filter here silently dropped every nested
    # route (only 6 of 288 real routes survived), turning this guardrail into a
    # false pass. `iter_route_contexts` is the helper FastAPI itself uses to walk
    # the real route tree (see fastapi/openapi/utils.py); each `RouteContext`
    # proxies `.path`/`.methods`/`.dependant`/`.endpoint` to the real route.
    routes = [
        context
        for context in iter_route_contexts(app.routes)
        if isinstance(context.original_route, APIRoute)
    ]

    unsecured = [
        f"{','.join(sorted(route.methods))} {route.path} -> {route.name}"
        for route in routes
        if not _is_route_secured(route) and not _path_is_allowlisted(route.path)
    ]

    assert not unsecured, "Routes missing auth dependency or explicit public allowlist:\n" + "\n".join(unsecured)
