"""
Foundational OTA adapter interfaces and orchestration services.
"""

from app.services.ota.contracts import (
    NormalizedOTAReservation,
    OTAAdapterContext,
    OTAOperationResult,
    OTAProviderAdapter,
)
from app.services.ota.orchestrator import OTAOrchestratorService
from app.services.ota.registry import build_default_ota_orchestrator, get_default_adapter

__all__ = [
    "NormalizedOTAReservation",
    "OTAAdapterContext",
    "OTAOperationResult",
    "OTAProviderAdapter",
    "OTAOrchestratorService",
    "build_default_ota_orchestrator",
    "get_default_adapter",
]
