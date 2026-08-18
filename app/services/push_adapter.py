"""
Web Push channel adapter.

Deliberately a thin, swappable interface rather than a full VAPID/aes128gcm
implementation: standards-based Web Push needs real crypto (VAPID JWT
signing + payload encryption) and an HTTP call per push service (Chrome,
Firefox, ...). That is a lot of surface to add and test correctly in one
pass. What matters for the outbox to be correct today is: the adapter shape,
the fail-closed gating (`WEB_PUSH_ENABLED` + `require_external_connections`,
same edge-gating convention as every other outbound integration in this
codebase), never logging subscription keys in plaintext, and treating
"subscription is gone" (410/404) as a permanent, non-retryable failure that
expires the subscription.

Follow-up: wire a real implementation (e.g. `pywebpush`) inside
`RealWebPushAdapter.send`, gated the same way.
"""
from __future__ import annotations

import logging

from app.config import get_settings
from app.models.notification import PushSubscription
from app.services.external_effects_policy import ExternalEffectsDisabled, require_external_connections

logger = logging.getLogger(__name__)


class WebPushSendError(RuntimeError):
    """Raised on a transient failure -- eligible for the outbox's normal retry."""


class WebPushSubscriptionInvalid(RuntimeError):
    """Raised when the push service reports the endpoint no longer exists
    (typically HTTP 404/410). The caller must expire the subscription and
    must NOT retry this send."""


class WebPushAdapter:
    """Adapter interface. `send` must never receive or log the payload body
    beyond what is passed here; callers are responsible for only passing
    already-redacted title/body text (see SAFE_PAYLOAD_KEYS discipline)."""

    def send(self, subscription: PushSubscription, *, title: str, body: str, url: str | None = None) -> None:
        raise NotImplementedError


class NullWebPushAdapter(WebPushAdapter):
    """Used whenever WEB_PUSH_ENABLED is false or no real implementation is
    wired -- fails closed and immediately (not a transient error), so the
    outbox does not burn retries on a permanent configuration gap."""

    def send(self, subscription: PushSubscription, *, title: str, body: str, url: str | None = None) -> None:
        raise WebPushSendError("Web Push is not enabled or not configured on this deployment")


class RealWebPushAdapter(WebPushAdapter):
    """Placeholder for a real VAPID Web Push implementation. Not wired yet
    (see module docstring) -- exists so `get_web_push_adapter()` has a
    concrete class to grow into without changing its call sites."""

    def send(self, subscription: PushSubscription, *, title: str, body: str, url: str | None = None) -> None:
        settings = get_settings()
        try:
            require_external_connections("web push send", settings)
        except ExternalEffectsDisabled as exc:
            raise WebPushSendError(str(exc)) from exc
        raise WebPushSendError("Web Push delivery is not implemented on this deployment yet")


def get_web_push_adapter() -> WebPushAdapter:
    settings = get_settings()
    if not bool(getattr(settings, "WEB_PUSH_ENABLED", False)):
        return NullWebPushAdapter()
    return RealWebPushAdapter()
