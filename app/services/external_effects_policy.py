"""Fail-closed policy gates for provider traffic and provider-originated events.

The guards in this module deliberately run at the edge of every integration,
before a caller loads/decrypts credentials, reads a request body, persists a
provider event, imports an SDK, or opens a network client.
"""
from __future__ import annotations

from app.config import Settings, get_settings


class ExternalEffectsDisabled(RuntimeError):
    """Raised when outbound provider traffic is disabled for this runtime."""


class InboundProviderEventsDisabled(RuntimeError):
    """Raised when provider-originated callbacks are disabled for this runtime."""


class GoogleLoginDisabled(RuntimeError):
    """Raised when Google Identity login is disabled for this runtime."""


class AppleLoginDisabled(RuntimeError):
    """Raised when Sign in with Apple is disabled for this runtime."""


def external_effects_enabled(settings: Settings | None = None) -> bool:
    return (settings or get_settings()).EXTERNAL_EFFECTS_ENABLED is True


def inbound_provider_events_enabled(settings: Settings | None = None) -> bool:
    return (settings or get_settings()).INBOUND_PROVIDER_EVENTS_ENABLED is True


def google_login_enabled(settings: Settings | None = None) -> bool:
    return (settings or get_settings()).GOOGLE_LOGIN_ENABLED is True


def apple_login_enabled(settings: Settings | None = None) -> bool:
    return (settings or get_settings()).APPLE_LOGIN_ENABLED is True


def external_connections_enabled(settings: Settings | None = None) -> bool:
    runtime_settings = settings or get_settings()
    return (
        runtime_settings.EXTERNAL_EFFECTS_ENABLED is True
        and runtime_settings.CONNECTIONS_ENABLED is True
    )


def require_external_effects(effect: str, settings: Settings | None = None) -> None:
    if not external_effects_enabled(settings):
        raise ExternalEffectsDisabled(
            f"{effect} is disabled by EXTERNAL_EFFECTS_ENABLED"
        )


def require_external_connections(effect: str, settings: Settings | None = None) -> None:
    runtime_settings = settings or get_settings()
    require_external_effects(effect, runtime_settings)
    if runtime_settings.CONNECTIONS_ENABLED is not True:
        raise ExternalEffectsDisabled(
            f"{effect} is disabled by CONNECTIONS_ENABLED"
        )


def require_inbound_provider_events(provider: str, settings: Settings | None = None) -> None:
    if not inbound_provider_events_enabled(settings):
        raise InboundProviderEventsDisabled(
            f"{provider} callbacks are disabled by INBOUND_PROVIDER_EVENTS_ENABLED"
        )


def require_google_login(settings: Settings | None = None) -> None:
    runtime_settings = settings or get_settings()
    if not google_login_enabled(runtime_settings):
        raise GoogleLoginDisabled(
            "Google login is disabled by GOOGLE_LOGIN_ENABLED"
        )
    try:
        require_external_connections("Google login", runtime_settings)
    except ExternalEffectsDisabled as exc:
        raise GoogleLoginDisabled(str(exc)) from exc


def require_apple_login(settings: Settings | None = None) -> None:
    runtime_settings = settings or get_settings()
    if not apple_login_enabled(runtime_settings):
        raise AppleLoginDisabled(
            "Apple login is disabled by APPLE_LOGIN_ENABLED"
        )
    try:
        require_external_connections("Apple login", runtime_settings)
    except ExternalEffectsDisabled as exc:
        raise AppleLoginDisabled(str(exc)) from exc
