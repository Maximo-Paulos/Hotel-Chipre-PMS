# Audit Hooks - Quick Reference

## TL;DR

Para agregar auditoría a un método de servicio:

```python
from app.decorators.audit_hooks import AuditContext, _entity_to_dict
from app.models.audit import ActionCodeEnum, EntityTypeEnum, SourceCodeEnum

def my_service_method(db: Session, entity, user_id: int):
    # 1. Capture BEFORE state
    before = _entity_to_dict(entity)
    
    # 2. Make changes
    entity.field = new_value
    db.flush()
    
    # 3. Capture AFTER state
    after = _entity_to_dict(entity)
    
    # 4. Record audit
    audit = AuditContext(db, user_id, entity.hotel_id)
    audit.record(
        entity_type=EntityTypeEnum.RESERVATION,  # or GUEST, ROOM, etc.
        action=ActionCodeEnum.UPDATE,             # or CREATE, DELETE, CANCEL, etc.
        entity_id=entity.id,
        before=before,
        after=after,
        change_summary="Description of what changed",
        source_code=SourceCodeEnum.API,           # or MANUAL, SYSTEM, OTA_SYNC
    )
    
    return entity
```

---

## API Rápida

### AuditContext

```python
audit = AuditContext(db: Session, user_id: int, hotel_id: int)

audit.record(
    entity_type: EntityTypeEnum,       # Required
    action: ActionCodeEnum,            # Required
    entity_id: Optional[int] = None,   # Usually required
    before: Optional[dict] = None,     # For UPDATE/DELETE
    after: Optional[dict] = None,      # For CREATE/UPDATE
    change_summary: Optional[str] = None,
    source_code: SourceCodeEnum = SourceCodeEnum.API,
    reason_code: Optional[str] = None,
)
```

### _entity_to_dict(entity)

Convierte una entidad SQLAlchemy a diccionario con todos sus campos.

```python
snapshot = _entity_to_dict(reservation)
# Result: {"id": 123, "confirmation_code": "RES-ABC123", "status": "draft", ...}
```

---

## Entity Types (EntityTypeEnum)

Usa estos en `entity_type=`:

```
RESERVATION              # Bookings
GUEST                    # Guest profiles
ROOM                     # Individual rooms
ROOM_CATEGORY            # Room types
RATE_PLAN                # Pricing plans
RATE_PLAN_PRICE          # Individual prices
SELLABLE_PRODUCT         # Add-ons (breakfast, etc.)
TAX_POLICY               # Tax rules
FX_POLICY                # Currency conversion
OTA_CONNECTION           # OTA integrations
OTA_PROPERTY_MAPPING     # Property mapping
OTA_RESERVATION_LINK     # OTA booking links
HOTEL_CONFIGURATION      # Hotel settings
HOTEL_MEMBERSHIP         # User roles/permissions
USER                     # Staff members
SECURITY_TOKEN           # API tokens/sessions
RESERVATION_ADJUSTMENT   # Price changes
ROOM_MOVE_EVENT          # Room changes during stay
BILLING_ADJUSTMENT       # Refunds, adjustments
```

---

## Action Codes (ActionCodeEnum)

Usa estos en `action=`:

```
CREATE       # Entidad nueva creada
UPDATE       # Entidad modificada
DELETE       # Entidad eliminada
CANCEL       # Reservación cancelada
APPROVE      # Aprobación de workflow
REJECT       # Rechazo de workflow
REVERT       # Deshacer cambio anterior
RESTORE      # Restaurar desde archivo
MERGE        # Fusionar dos entidades
SPLIT        # Dividir entidad
```

---

## Source Codes (SourceCodeEnum)

Usa estos en `source_code=`:

```
API           # Llamada HTTP
MANUAL        # Acción UI/usuario
SYSTEM        # Auto-triggered (job, timeout)
OTA_SYNC      # Sincronización automática
ADMIN_BULK    # Operación batch
IMPORT        # Data import/migration
WEBHOOK       # Webhook entrante
```

**Default:** `API`

---

## Patrones Comunes

### CREATE (nueva entidad)

```python
def create_entity(db, data, hotel_id, user_id):
    entity = Entity(hotel_id=hotel_id, **data)
    db.add(entity)
    db.flush()
    
    audit = AuditContext(db, user_id, hotel_id)
    audit.record(
        entity_type=EntityTypeEnum.GUEST,
        action=ActionCodeEnum.CREATE,
        entity_id=entity.id,
        after=_entity_to_dict(entity),
        change_summary=f"Created {entity.name}",
    )
    return entity
```

### UPDATE (cambio de entidad)

```python
def update_entity(db, entity_id, data, user_id):
    entity = db.query(Entity).get(entity_id)
    before = _entity_to_dict(entity)
    
    entity.field = data.field
    db.flush()
    
    after = _entity_to_dict(entity)
    
    audit = AuditContext(db, user_id, entity.hotel_id)
    audit.record(
        entity_type=EntityTypeEnum.GUEST,
        action=ActionCodeEnum.UPDATE,
        entity_id=entity_id,
        before=before,
        after=after,
        change_summary=f"Updated {entity.field}",
    )
    return entity
```

### DELETE (eliminación lógica o física)

```python
def delete_entity(db, entity_id, user_id):
    entity = db.query(Entity).get(entity_id)
    before = _entity_to_dict(entity)
    
    entity.deleted_at = datetime.now(timezone.utc)  # soft delete
    db.flush()
    
    audit = AuditContext(db, user_id, entity.hotel_id)
    audit.record(
        entity_type=EntityTypeEnum.GUEST,
        action=ActionCodeEnum.DELETE,
        entity_id=entity_id,
        before=before,
        after=_entity_to_dict(entity),
        change_summary="Deleted",
    )
```

### CANCEL (cancelación de reservación)

```python
def cancel_reservation(db, res_id, reason, user_id):
    res = db.query(Reservation).get(res_id)
    before = _entity_to_dict(res)
    
    res.status = ReservationStatusEnum.CANCELLED
    res.cancelled_at = datetime.now(timezone.utc)
    db.flush()
    
    audit = AuditContext(db, user_id, res.hotel_id)
    audit.record(
        entity_type=EntityTypeEnum.RESERVATION,
        action=ActionCodeEnum.CANCEL,
        entity_id=res_id,
        before=before,
        after=_entity_to_dict(res),
        change_summary=f"Cancelled: {reason}",
        reason_code=reason,
    )
```

### MULTI-ENTITY (múltiples entidades en una operación)

```python
def checkin(db, res_id, user_id):
    res = db.query(Reservation).get(res_id)
    room = db.query(Room).get(res.room_id)
    
    audit = AuditContext(db, user_id, res.hotel_id)
    
    # Log reservation change
    res_before = _entity_to_dict(res)
    res.status = ReservationStatusEnum.CHECKED_IN
    res.actual_check_in = datetime.now(timezone.utc)
    db.flush()
    
    audit.record(
        entity_type=EntityTypeEnum.RESERVATION,
        action=ActionCodeEnum.UPDATE,
        entity_id=res.id,
        before=res_before,
        after=_entity_to_dict(res),
        change_summary="Guest checked in",
        source_code=SourceCodeEnum.MANUAL,
    )
    
    # Log room status change
    room_before = _entity_to_dict(room)
    room.status = RoomStatusEnum.OCCUPIED
    db.flush()
    
    audit.record(
        entity_type=EntityTypeEnum.ROOM,
        action=ActionCodeEnum.UPDATE,
        entity_id=room.id,
        before=room_before,
        after=_entity_to_dict(room),
        change_summary="Room occupied",
        source_code=SourceCodeEnum.SYSTEM,
    )
```

---

## Errores Comunes

### ❌ No capturar estado ANTES antes de cambiar

```python
# MALO
entity.field = new_value
db.flush()
after = _entity_to_dict(entity)

# BUENO
before = _entity_to_dict(entity)
entity.field = new_value
db.flush()
after = _entity_to_dict(entity)
```

### ❌ Entity ID no coincide con Entity Type

```python
# MALO
entity_type=EntityTypeEnum.RESERVATION,
entity_id=guest.id,  # WRONG! Es guest ID, no reservation ID

# BUENO
entity_type=EntityTypeEnum.RESERVATION,
entity_id=reservation.id,
```

### ❌ Olvidar hotel_id en AuditContext

```python
# MALO
audit = AuditContext(db, user_id, None)

# BUENO
audit = AuditContext(db, user_id, entity.hotel_id)
```

### ❌ Falla de audit rompe operación

```python
# MALO - error en audit rompe main operation
audit_service.record_change(...)  # Si falla, excepción no capturada

# BUENO - AuditContext ya maneja esto
audit = AuditContext(db, user_id, hotel_id)
audit.record(...)  # Falla de audit no afecta main flow
```

---

## Verificación en Tests

```python
from app.models.audit import HotelAuditEvent

# Query audit event
event = db.query(HotelAuditEvent).filter(
    HotelAuditEvent.entity_type == EntityTypeEnum.RESERVATION,
    HotelAuditEvent.entity_id == res_id,
    HotelAuditEvent.action_code == ActionCodeEnum.CREATE,
).first()

assert event is not None
assert event.user_id == user_id
assert event.hotel_id == hotel_id
assert event.before_json is None  # No before para CREATE
assert event.after_json is not None

# Check before/after
import json
after_data = json.loads(event.after_json)
assert after_data["field"] == expected_value
```

---

## Ubicación de Código

- **Decoradores:** `app/decorators/audit_hooks.py`
- **Modelos:** `app/models/audit.py`
- **Service:** `app/services/audit_service.py`
- **Tests:** `app/tests/test_audit_hooks.py`
- **Guía completa:** `AUDIT_HOOKS_INTEGRATION_GUIDE.md`

---

## Imports Necesarios

```python
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.decorators.audit_hooks import AuditContext, _entity_to_dict
from app.models.audit import ActionCodeEnum, EntityTypeEnum, SourceCodeEnum
```

---

## Servir Hooks en 5 Servicios

1. **reservation_service.py** - CREATE, UPDATE, CANCEL
2. **payment_service.py** - CREATE (transactions), UPDATE (status)
3. **checkin_service.py** - CHECK_IN, CHECK_OUT
4. **guest_service.py** - CREATE, UPDATE
5. **hotel_service.py** - UPDATE (config), CREATE (membership)

Ver `AUDIT_HOOKS_INTEGRATION_GUIDE.md` para ejemplos completos.
