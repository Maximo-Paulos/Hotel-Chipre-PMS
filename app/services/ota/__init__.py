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

__all__ = [
    "NormalizedOTAReservation",
    "OTAAdapterContext",
    "OTAOperationResult",
    "OTAProviderAdapter",
    "OTAOrchestratorService",
]
