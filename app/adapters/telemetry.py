"""Minimal telemetry port; the application is provider-neutral by default."""
from __future__ import annotations

import logging
from typing import Any, Protocol


class Telemetry(Protocol):
    def record(self, name: str, *, fields: dict[str, Any] | None = None) -> None: ...


class LoggingTelemetry:
    def __init__(self, logger: logging.Logger | None = None):
        self._logger = logger or logging.getLogger("hotel_pms.telemetry")

    def record(self, name: str, *, fields: dict[str, Any] | None = None) -> None:
        # Callers provide only bounded operational fields; business payloads
        # and bound SQL values must never be placed in telemetry.
        self._logger.info("telemetry.%s", name, extra=fields or {})
