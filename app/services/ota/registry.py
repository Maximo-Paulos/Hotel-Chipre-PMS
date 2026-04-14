"""
Default OTA adapter registry.

This keeps provider construction in one place so the legacy runtime and the new
orchestrator can share the same adapter instances and normalization rules.
"""
from __future__ import annotations

from app.services.ota.adapters import BookingAdapter, DespegarAdapter, ExpediaAdapter
from app.services.ota.contracts import OTAProviderAdapter
from app.services.ota.orchestrator import OTAOrchestratorService


def build_default_ota_orchestrator() -> OTAOrchestratorService:
    orchestrator = OTAOrchestratorService()
    for adapter in (BookingAdapter(), ExpediaAdapter(), DespegarAdapter()):
        orchestrator.register_adapter(adapter)
    return orchestrator


def get_default_adapter(provider_code: str) -> OTAProviderAdapter:
    return build_default_ota_orchestrator().get_adapter(provider_code)
