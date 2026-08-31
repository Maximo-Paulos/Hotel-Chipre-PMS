"""Authenticated field-level collaboration endpoints.

Drafts are ephemeral and safe-by-allowlist.  A persisted edit still goes
through a normal tenant-scoped SQLAlchemy transaction and the server remains
the authority.  Financial and reservation lifecycle actions are deliberately
absent from the collaborative resource registry; they stay on their atomic,
audited endpoints.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
import secrets
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any

import redis.asyncio as redis_async
from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect, status
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.database import get_db
from app.dependencies.auth import AuthContext, get_auth_context
from app.models.audit_log import AuditActionEnum
from app.models.hotel_membership import HotelMembership
from app.models.user import User
from app.schemas.collaboration import (
    CollaborationPatchRequest,
    CollaborationTicketRequest,
    CollaborationTicketResponse,
)
from app.services.collaboration import (
    apply_resource_changes,
    editable_resource_values,
    get_resource,
    get_resource_spec,
    merge_field_changes,
    normalize_resource_type,
    resource_revision,
    resource_version,
    serialize_resource,
    validate_draft_changes,
)
from app.services import audit_log_service
from app.services.domain_events import RealtimeEventsUnavailable, get_realtime_client
from app.services.permission_service import audit_permission_denied, resolve
from app.services.reservation_service import ReservationError


logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/collaboration", tags=["Collaboration"])

TICKET_KEY_TEMPLATE = "hotel:{hotel_id}:collaboration:ticket:{digest}"
TICKET_CONSUME_SCRIPT = "local value = redis.call('GET', KEYS[1]); if value then redis.call('DEL', KEYS[1]); end; return value"
COLLABORATION_ROOM_TEMPLATE = "hotel:{hotel_id}:collaboration:{resource_type}:{resource_id}"


def _ticket_key(hotel_id: int, raw_ticket: str) -> str:
    digest = hashlib.sha256(raw_ticket.encode("utf-8")).hexdigest()
    return TICKET_KEY_TEMPLATE.format(hotel_id=hotel_id, digest=digest)


def _require_permission(db: Session, context: AuthContext, permission: str) -> None:
    if not context.is_verified:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Verifica tu email para usar el sistema")
    if resolve(db, context.hotel_id, context.user_role, permission, user_id=context.user_id):
        permissions = context.permissions or set()
        permissions.add(permission)
        context.permissions = permissions
        return
    audit_permission_denied(
        db,
        hotel_id=context.hotel_id,
        user_id=context.user_id,
        role=context.user_role,
        permission_code=permission,
    )
    raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenes permisos para esta accion")


def _require_resource_lane(context: AuthContext, resource_type: str) -> None:
    """Keep collaboration permissions aligned with the normal resource API."""

    # ``room:status_update`` is intentionally also available to housekeeping,
    # but the generic room PATCH endpoint only lets owner/co-owner/manager
    # edit room metadata.  Collaboration must not create a broader write path.
    if normalize_resource_type(resource_type) == "room" and context.user_role not in {"owner", "co_owner", "manager"}:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No tenes permisos para editar la habitación")


def _realtime_client_or_503():
    try:
        client = get_realtime_client()
    except RealtimeEventsUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Colaboracion no disponible: Redis/Valkey no responde",
        ) from exc
    if client is None:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Colaboracion no disponible: Redis/Valkey no responde",
        )
    return client


@router.post("/tickets", response_model=CollaborationTicketResponse)
def create_collaboration_ticket(
    data: CollaborationTicketRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    """Issue a short-lived, one-use ticket for one tenant resource."""

    try:
        resource_type = normalize_resource_type(data.resource_type)
        spec = get_resource_spec(resource_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    # A collaboration ticket is an editing capability, not a read bypass.
    _require_permission(db, context, spec.read_permission)
    _require_permission(db, context, spec.write_permission)
    _require_resource_lane(context, resource_type)
    if context.user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario no disponible para coedición")
    resource = get_resource(db, resource_type, data.resource_id, context.hotel_id)
    if resource is None:
        # Permission is checked first; after that a foreign resource is
        # indistinguishable from an absent one.
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado")

    client = _realtime_client_or_503()
    settings = get_settings()
    ttl = max(5, min(int(settings.COLLABORATION_TICKET_TTL_SECONDS), 300))
    raw_ticket = secrets.token_urlsafe(32)
    claims = {
        "hotel_id": context.hotel_id,
        "user_id": context.user_id,
        "user_role": context.user_role,
        "resource_type": resource_type,
        "resource_id": data.resource_id,
        "read_permission": spec.read_permission,
        "write_permission": spec.write_permission,
        "allowed_fields": sorted(spec.editable_fields),
        "issued_at": int(time.time()),
    }
    try:
        client.setex(_ticket_key(context.hotel_id, raw_ticket), ttl, json.dumps(claims, separators=(",", ":")))
    except Exception as exc:
        logger.warning("collaboration.ticket_store_failed", extra={"hotel_id": context.hotel_id, "error_type": type(exc).__name__})
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Colaboracion no disponible: no se pudo emitir el ticket",
        ) from exc
    return CollaborationTicketResponse(
        ticket=raw_ticket,
        expires_in=ttl,
        resource_type=resource_type,
        resource_id=data.resource_id,
    )


def _patch_conflict_response(
    *,
    server_resource: dict[str, Any],
    server_revision: str,
    conflicting_fields: tuple[str, ...] | list[str],
) -> HTTPException:
    return HTTPException(
        status_code=status.HTTP_409_CONFLICT,
        detail={
            "code": "COLLABORATION_CONFLICT",
            "message": "El recurso cambio mientras lo estabas editando",
            "server_revision": server_revision,
            "server_resource": server_resource,
            "conflicting_fields": list(conflicting_fields),
        },
    )


@router.patch("/resources/{resource_type}/{resource_id}")
def patch_collaborative_resource(
    resource_type: str,
    resource_id: int,
    data: CollaborationPatchRequest,
    db: Session = Depends(get_db),
    context: AuthContext = Depends(get_auth_context),
):
    """Persist an optimistic, field-level merge under the current tenant."""

    try:
        canonical_type = normalize_resource_type(resource_type)
        spec = get_resource_spec(canonical_type)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc)) from exc

    _require_permission(db, context, spec.read_permission)
    _require_permission(db, context, spec.write_permission)
    _require_resource_lane(context, canonical_type)
    if context.user_id is None:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Usuario no disponible para coedición")
    resource = get_resource(
        db,
        canonical_type,
        resource_id,
        context.hotel_id,
        lock_for_update=True,
    )
    if resource is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Recurso no encontrado")

    try:
        settings = get_settings()
        max_patch_fields = max(1, min(int(settings.COLLABORATION_MAX_PATCH_FIELDS), 100))
        changes = validate_draft_changes(canonical_type, data.changes, max_fields=max_patch_fields)
        current_values = editable_resource_values(canonical_type, resource)
        current_revision = resource_revision(current_values)
        if data.base_revision != current_revision:
            base_values = validate_draft_changes(canonical_type, data.base_values, max_fields=max_patch_fields)
            merged = merge_field_changes(current_values, base_values, changes)
            if merged.conflicting_fields:
                raise _patch_conflict_response(
                    server_resource=serialize_resource(canonical_type, resource),
                    server_revision=current_revision,
                    conflicting_fields=merged.conflicting_fields,
                )
            changes = {
                field: merged.values[field]
                for field in changes
                if merged.values.get(field) != current_values.get(field)
            }

        if changes:
            apply_resource_changes(
                db,
                canonical_type,
                resource,
                changes,
                hotel_id=context.hotel_id,
                user_id=context.user_id,
                actor_role=context.user_role,
            )
            # Persist collaboration edits in the same transaction as the
            # authoritative resource. Store field names only; values may be
            # guest contact data or operational notes and do not belong in an
            # audit payload or realtime event.
            audit_log_service.safe_create_audit_log(
                db,
                hotel_id=context.hotel_id,
                table_name=str(getattr(resource, "__tablename__", canonical_type)),
                record_id=resource_id,
                action=AuditActionEnum.UPDATE,
                actor_user_id=context.user_id,
                payload_before={"changed_fields": sorted(changes)},
                payload_after={"changed_fields": sorted(changes), "source": "collaboration"},
            )
        db.commit()
        db.refresh(resource)
    except HTTPException:
        db.rollback()
        raise
    except (ReservationError, ValueError) as exc:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "COLLABORATION_VALIDATION_FAILED", "message": str(exc)},
        ) from exc
    except (IntegrityError, SQLAlchemyError) as exc:
        db.rollback()
        logger.warning(
            "collaboration.patch_failed",
            extra={"hotel_id": context.hotel_id, "resource_type": canonical_type, "error_type": type(exc).__name__},
        )
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "COLLABORATION_WRITE_CONFLICT", "message": "No se pudo guardar el cambio"},
        ) from exc

    updated_values = serialize_resource(canonical_type, resource)
    return {
        "resource_type": canonical_type,
        "resource_id": resource_id,
        "resource": updated_values,
        "revision": resource_revision(updated_values),
        "version": resource_version(resource),
    }


def _consume_ticket(client: Any, hotel_id: int, raw_ticket: str) -> dict[str, Any] | None:
    if not isinstance(raw_ticket, str) or not raw_ticket or len(raw_ticket) > 256:
        return None
    key = _ticket_key(hotel_id, raw_ticket)
    try:
        getdel = getattr(client, "getdel", None)
        if callable(getdel):
            raw_claims = getdel(key)
        else:
            try:
                raw_claims = client.eval(TICKET_CONSUME_SCRIPT, 1, key)
            except Exception:
                # Compatibility fallback for small test doubles and old Redis
                # versions. Production Redis 5+ uses GETDEL or the Lua path.
                raw_claims = client.get(key)
                if raw_claims is not None:
                    client.delete(key)
    except Exception as exc:
        logger.warning("collaboration.ticket_consume_failed", extra={"hotel_id": hotel_id, "error_type": type(exc).__name__})
        return None
    if raw_claims is None:
        return None
    if isinstance(raw_claims, bytes):
        raw_claims = raw_claims.decode("utf-8", errors="replace")
    try:
        claims = json.loads(raw_claims)
    except (TypeError, json.JSONDecodeError):
        return None
    return claims if isinstance(claims, dict) else None


def _live_ticket_is_authorized(db: Session, claims: dict[str, Any]) -> bool:
    try:
        hotel_id = int(claims["hotel_id"])
        user_id = int(claims["user_id"])
        resource_id = int(claims["resource_id"])
        resource_type = normalize_resource_type(claims["resource_type"])
        spec = get_resource_spec(resource_type)
    except (KeyError, TypeError, ValueError):
        return False
    user = db.query(User).filter(User.id == user_id, User.is_active.is_(True), User.is_verified.is_(True)).one_or_none()
    membership = (
        db.query(HotelMembership)
        .filter(
            HotelMembership.hotel_id == hotel_id,
            HotelMembership.user_id == user_id,
            HotelMembership.status == "active",
        )
        .one_or_none()
    )
    if user is None or membership is None:
        return False
    if claims.get("allowed_fields") != sorted(spec.editable_fields):
        return False
    if not resolve(db, hotel_id, membership.role, spec.read_permission, user_id=user_id):
        return False
    if not resolve(db, hotel_id, membership.role, spec.write_permission, user_id=user_id):
        return False
    if resource_type == "room" and membership.role not in {"owner", "co_owner", "manager"}:
        return False
    return get_resource(db, resource_type, resource_id, hotel_id) is not None


def _room_name(hotel_id: int, resource_type: str, resource_id: int) -> str:
    return COLLABORATION_ROOM_TEMPLATE.format(
        hotel_id=hotel_id,
        resource_type=normalize_resource_type(resource_type),
        resource_id=resource_id,
    )


@dataclass(slots=True)
class _Peer:
    websocket: WebSocket
    connection_id: str
    user_id: int
    send_lock: asyncio.Lock = field(default_factory=asyncio.Lock)
    timestamps: deque[float] = field(default_factory=deque)


@dataclass(slots=True)
class _RoomTransport:
    client: Any
    pubsub: Any
    task: asyncio.Task


class CollaborationManager:
    """Process-local peers plus best-effort Redis pub/sub fan-out."""

    def __init__(self) -> None:
        self._rooms: dict[str, dict[str, _Peer]] = {}
        self._transports: dict[str, _RoomTransport] = {}
        self._transport_retry_tasks: dict[str, asyncio.Task] = {}
        self._lock = asyncio.Lock()

    async def join(self, room: str, peer: _Peer) -> None:
        async with self._lock:
            self._rooms.setdefault(room, {})[peer.connection_id] = peer
            if room not in self._transports:
                await self._start_transport(room)
            if room not in self._transports and room not in self._transport_retry_tasks:
                self._transport_retry_tasks[room] = asyncio.create_task(self._retry_transport(room))

    async def leave(self, room: str, connection_id: str) -> None:
        async with self._lock:
            peers = self._rooms.get(room)
            if peers is None:
                return
            peers.pop(connection_id, None)
            if peers:
                return
            self._rooms.pop(room, None)
            transport = self._transports.pop(room, None)
            retry_task = self._transport_retry_tasks.pop(room, None)
        if retry_task is not None:
            retry_task.cancel()
            try:
                await retry_task
            except asyncio.CancelledError:
                pass
        if transport is not None:
            transport.task.cancel()
            try:
                await transport.task
            except asyncio.CancelledError:
                pass

    async def _start_transport(self, room: str) -> None:
        client = None
        pubsub = None
        try:
            client = redis_async.from_url(get_settings().REDIS_URL, decode_responses=True)
            pubsub = client.pubsub(ignore_subscribe_messages=True)
            await pubsub.subscribe(f"{room}:drafts")
            task = asyncio.create_task(self._listen(room, client, pubsub))
            self._transports[room] = _RoomTransport(client=client, pubsub=pubsub, task=task)
        except Exception as exc:
            logger.warning("collaboration.redis_subscribe_failed", extra={"error_type": type(exc).__name__})
            for resource in (pubsub, client):
                close = getattr(resource, "aclose", None) or getattr(resource, "close", None)
                if close is not None:
                    try:
                        result = close()
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        pass

    async def _listen(self, room: str, client: Any, pubsub: Any) -> None:
        cancelled = False
        try:
            while True:
                message = await pubsub.get_message(ignore_subscribe_messages=True, timeout=1.0)
                if message and message.get("type") == "message":
                    raw = message.get("data")
                    try:
                        envelope = json.loads(raw)
                    except (TypeError, json.JSONDecodeError):
                        continue
                    if isinstance(envelope, dict):
                        await self._broadcast_local(
                            room,
                            envelope.get("payload"),
                            skip_connection_id=envelope.get("sender_connection_id"),
                        )
                await asyncio.sleep(0)
        except asyncio.CancelledError:
            cancelled = True
            raise
        except Exception as exc:
            logger.warning("collaboration.redis_listener_failed", extra={"error_type": type(exc).__name__})
        finally:
            for resource in (pubsub, client):
                close = getattr(resource, "aclose", None) or getattr(resource, "close", None)
                if close is not None:
                    try:
                        result = close()
                        if asyncio.iscoroutine(result):
                            await result
                    except Exception:
                        pass
        if cancelled:
            return
        async with self._lock:
            current = self._transports.get(room)
            if current is not None and current.task is asyncio.current_task():
                self._transports.pop(room, None)
            if self._rooms.get(room) and room not in self._transport_retry_tasks:
                retry_task = asyncio.create_task(self._retry_transport(room))
                self._transport_retry_tasks[room] = retry_task

    async def _retry_transport(self, room: str) -> None:
        delay = 1.0
        try:
            while True:
                await asyncio.sleep(delay)
                async with self._lock:
                    if not self._rooms.get(room) or room in self._transports:
                        return
                    await self._start_transport(room)
                    if room in self._transports:
                        return
                delay = min(delay * 2, 30.0)
        finally:
            current = self._transport_retry_tasks.get(room)
            if current is asyncio.current_task():
                self._transport_retry_tasks.pop(room, None)

    async def publish(self, room: str, payload: dict[str, Any], *, sender_connection_id: str) -> None:
        envelope = {"sender_connection_id": sender_connection_id, "payload": payload}
        raw = json.dumps(envelope, separators=(",", ":"), ensure_ascii=True)
        transport = self._transports.get(room)
        if transport is not None:
            try:
                await transport.client.publish(f"{room}:drafts", raw)
                return
            except Exception as exc:
                logger.warning("collaboration.redis_publish_failed", extra={"error_type": type(exc).__name__})
        await self._broadcast_local(room, payload, skip_connection_id=sender_connection_id)

    async def _broadcast_local(self, room: str, payload: Any, *, skip_connection_id: str | None = None) -> None:
        if not isinstance(payload, dict):
            return
        peers = list(self._rooms.get(room, {}).values())
        for peer in peers:
            if peer.connection_id == skip_connection_id:
                continue
            try:
                async with peer.send_lock:
                    await peer.websocket.send_json(payload)
            except Exception:
                await self.leave(room, peer.connection_id)


collaboration_manager = CollaborationManager()


def _message_allowed(peer: _Peer) -> bool:
    now = time.monotonic()
    settings = get_settings()
    limit = max(10, int(settings.COLLABORATION_RATE_LIMIT_PER_MINUTE))
    while peer.timestamps and peer.timestamps[0] <= now - 60:
        peer.timestamps.popleft()
    if len(peer.timestamps) >= limit:
        return False
    peer.timestamps.append(now)
    return True


async def _send_peer(peer: _Peer, payload: dict[str, Any]) -> None:
    async with peer.send_lock:
        await peer.websocket.send_json(payload)


@router.websocket("/ws")
async def collaboration_websocket(websocket: WebSocket, db: Session = Depends(get_db)):
    """Authenticate with a one-use ticket, then exchange safe draft signals."""

    await websocket.accept()
    peer: _Peer | None = None
    room: str | None = None
    try:
        settings = get_settings()
        raw_handshake = await asyncio.wait_for(websocket.receive_text(), timeout=10)
        if len(raw_handshake.encode("utf-8")) > int(settings.COLLABORATION_MAX_WS_MESSAGE_BYTES):
            await websocket.close(code=1009, reason="Mensaje demasiado grande")
            return
        try:
            handshake = json.loads(raw_handshake)
        except (TypeError, json.JSONDecodeError):
            await websocket.close(code=4401, reason="Ticket invalido")
            return
        if not isinstance(handshake, dict) or not isinstance(handshake.get("ticket"), str):
            await websocket.close(code=4401, reason="Ticket invalido")
            return
        # The ticket is tenant-bound, so the hotel id is carried inside the
        # claim. We first use the backend's configured client to atomically
        # consume it, then verify the live membership and permissions below.
        try:
            client = get_realtime_client()
        except RealtimeEventsUnavailable:
            client = None
        if client is None:
            await websocket.close(code=1013, reason="Realtime no disponible")
            return
        # Tickets are only accepted after decoding their signed-by-storage
        # tenant binding. We need a bounded candidate hotel id to locate the
        # key; the browser cannot choose a different tenant because the claim
        # is verified against the same key after consumption. The client sends
        # the hotel header when possible, otherwise the ticket handshake may
        # include a positive hotel_id solely as a lookup hint.
        hinted_hotel_id = websocket.headers.get("x-hotel-id") or handshake.get("hotel_id")
        try:
            hinted_hotel_id = int(hinted_hotel_id)
        except (TypeError, ValueError):
            hinted_hotel_id = 0
        if hinted_hotel_id <= 0:
            await websocket.close(code=4401, reason="Hotel requerido")
            return
        claims = _consume_ticket(client, hinted_hotel_id, handshake["ticket"])
        if claims is None or int(claims.get("hotel_id", 0)) != hinted_hotel_id or not _live_ticket_is_authorized(db, claims):
            await websocket.close(code=4401, reason="Ticket invalido o expirado")
            return
        # The database is needed only for the bounded ticket/membership check.
        # Do not hold a synchronous SQLAlchemy connection for the lifetime of
        # an otherwise asynchronous collaboration socket.
        db.close()

        resource_type = normalize_resource_type(claims["resource_type"])
        resource_id = int(claims["resource_id"])
        room = _room_name(hinted_hotel_id, resource_type, resource_id)
        peer = _Peer(
            websocket=websocket,
            connection_id=secrets.token_urlsafe(12),
            user_id=int(claims["user_id"]),
        )
        await collaboration_manager.join(room, peer)
        await _send_peer(
            peer,
            {
                "type": "ready",
                "connection_id": peer.connection_id,
                "resource_type": resource_type,
                "resource_id": resource_id,
            },
        )
        await collaboration_manager.publish(
            room,
            {
                "type": "presence",
                "event": "joined",
                "connection_id": peer.connection_id,
                "user_id": peer.user_id,
                "fields": [],
            },
            sender_connection_id=peer.connection_id,
        )

        while True:
            try:
                raw_message = await asyncio.wait_for(websocket.receive_text(), timeout=30)
            except asyncio.TimeoutError:
                await _send_peer(peer, {"type": "ping"})
                continue
            if len(raw_message.encode("utf-8")) > int(settings.COLLABORATION_MAX_WS_MESSAGE_BYTES):
                await websocket.close(code=1009, reason="Mensaje demasiado grande")
                return
            if not _message_allowed(peer):
                await websocket.close(code=1008, reason="Demasiados mensajes")
                return
            try:
                message = json.loads(raw_message)
            except (TypeError, json.JSONDecodeError):
                await _send_peer(peer, {"type": "error", "code": "INVALID_MESSAGE"})
                continue
            if not isinstance(message, dict):
                await _send_peer(peer, {"type": "error", "code": "INVALID_MESSAGE"})
                continue
            message_type = message.get("type")
            if message_type == "ping":
                await _send_peer(peer, {"type": "pong"})
                continue
            if message_type == "presence":
                raw_fields = message.get("fields", [])
                spec = get_resource_spec(resource_type)
                fields = sorted(
                    {field for field in raw_fields if isinstance(field, str) and field in spec.editable_fields}
                ) if isinstance(raw_fields, list) else []
                await collaboration_manager.publish(
                    room,
                    {
                        "type": "presence",
                        "event": "updated",
                        "connection_id": peer.connection_id,
                        "user_id": peer.user_id,
                        "fields": fields,
                    },
                    sender_connection_id=peer.connection_id,
                )
                continue
            if message_type == "draft_patch":
                try:
                    max_patch_fields = max(1, min(int(settings.COLLABORATION_MAX_PATCH_FIELDS), 100))
                    changes = validate_draft_changes(
                        resource_type,
                        message.get("changes", {}),
                        max_fields=max_patch_fields,
                    )
                    base_revision = message.get("base_revision")
                    if not isinstance(base_revision, str) or len(base_revision) > 128:
                        raise ValueError("Invalid base revision")
                except ValueError:
                    await _send_peer(peer, {"type": "error", "code": "INVALID_DRAFT"})
                    continue
                await collaboration_manager.publish(
                    room,
                    {
                        "type": "draft_patch",
                        "connection_id": peer.connection_id,
                        "user_id": peer.user_id,
                        "base_revision": base_revision,
                        "changes": changes,
                    },
                    sender_connection_id=peer.connection_id,
                )
                continue
            # Persisted changes must use PATCH so the server can lock, merge,
            # validate and audit them. Never turn an arbitrary WS message into
            # a transactional operation.
            await _send_peer(peer, {"type": "error", "code": "UNSUPPORTED_MESSAGE"})
    except WebSocketDisconnect:
        return
    except (KeyError, TypeError, ValueError):
        try:
            await websocket.close(code=4401, reason="Ticket invalido")
        except Exception:
            pass
    finally:
        if peer is not None and room is not None:
            await collaboration_manager.publish(
                room,
                {
                    "type": "presence",
                    "event": "left",
                    "connection_id": peer.connection_id,
                    "user_id": peer.user_id,
                    "fields": [],
                },
                sender_connection_id=peer.connection_id,
            )
            await collaboration_manager.leave(room, peer.connection_id)
