"""
OTA orchestrator service.

This layer coordinates provider adapters, persistent sync jobs and sync events
without forcing the rest of the PMS to know channel-specific details.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy.orm import Session

from app.models.ota_core import OTAConnection, OTAProvider, OTASyncEvent, OTASyncJob
from app.services.ota.contracts import OTAAdapterContext, OTAOperationResult, OTAProviderAdapter


class OTAOrchestratorError(Exception):
    pass


class OTAOrchestratorService:
    def __init__(self) -> None:
        self._adapters: dict[str, OTAProviderAdapter] = {}

    def register_adapter(self, adapter: OTAProviderAdapter) -> None:
        self._adapters[adapter.provider_code] = adapter

    def get_adapter(self, provider_code: str) -> OTAProviderAdapter:
        adapter = self._adapters.get(provider_code)
        if adapter is None:
            raise OTAOrchestratorError(f"No OTA adapter registered for provider '{provider_code}'")
        return adapter

    def build_context(self, db: Session, connection_id: int) -> OTAAdapterContext:
        connection = db.get(OTAConnection, connection_id)
        if connection is None:
            raise OTAOrchestratorError(f"OTA connection {connection_id} not found")
        provider = db.get(OTAProvider, connection.provider_id)
        if provider is None:
            raise OTAOrchestratorError(f"OTA provider {connection.provider_id} not found")
        return OTAAdapterContext(
            hotel_id=connection.hotel_id,
            provider_code=provider.code,
            connection_id=connection.id,
            environment=connection.environment,
            external_property_id=connection.external_property_id,
            auth_config=self._load_json(connection.auth_config_encrypted),
            settings=self._load_json(connection.settings_json),
        )

    def create_sync_job(
        self,
        db: Session,
        *,
        hotel_id: int,
        provider_id: int,
        connection_id: int | None,
        job_type: str,
        scope_type: str | None = None,
        scope_id: str | None = None,
        status: str = "pending",
    ) -> OTASyncJob:
        job = OTASyncJob(
            hotel_id=hotel_id,
            provider_id=provider_id,
            connection_id=connection_id,
            job_type=job_type,
            scope_type=scope_type,
            scope_id=scope_id,
            status=status,
        )
        db.add(job)
        db.flush()
        return job

    def record_event(
        self,
        db: Session,
        *,
        job_id: int,
        hotel_id: int,
        provider_id: int,
        event_type: str,
        result: str,
        message: str | None = None,
        request_payload: dict[str, Any] | str | None = None,
        response_payload: dict[str, Any] | str | None = None,
        http_status: int | None = None,
    ) -> OTASyncEvent:
        event = OTASyncEvent(
            job_id=job_id,
            hotel_id=hotel_id,
            provider_id=provider_id,
            event_type=event_type,
            result=result,
            message=message,
            request_payload_encrypted=self._serialize_payload(request_payload),
            response_payload_encrypted=self._serialize_payload(response_payload),
            http_status=http_status,
        )
        db.add(event)
        db.flush()
        return event

    def verify_connection(self, db: Session, connection_id: int) -> OTAOperationResult:
        connection = db.get(OTAConnection, connection_id)
        if connection is None:
            raise OTAOrchestratorError(f"OTA connection {connection_id} not found")
        context = self.build_context(db, connection_id)
        adapter = self.get_adapter(context.provider_code)
        job = self.create_sync_job(
            db,
            hotel_id=connection.hotel_id,
            provider_id=connection.provider_id,
            connection_id=connection.id,
            job_type="verify_connection",
            status="running",
        )
        result = adapter.verify_connection(context)
        connection.status = "healthy" if result.success else "error"
        connection.last_error = None if result.success else (result.message or "verification_failed")
        job.status = "succeeded" if result.success else "failed"
        self.record_event(
            db,
            job_id=job.id,
            hotel_id=connection.hotel_id,
            provider_id=connection.provider_id,
            event_type="verify_connection",
            result=job.status,
            message=result.message,
            request_payload=result.raw_request,
            response_payload=result.raw_response or result.payload,
            http_status=result.http_status,
        )
        db.flush()
        return result

    @staticmethod
    def _load_json(value: str | None) -> dict[str, Any]:
        if not value:
            return {}
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}

    @staticmethod
    def _serialize_payload(payload: dict[str, Any] | str | None) -> str | None:
        if payload is None:
            return None
        if isinstance(payload, str):
            return payload
        return json.dumps(payload, ensure_ascii=True, sort_keys=True)
