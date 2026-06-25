# Guía de Integración: Hooks de Auditoría

## Resumen

Este documento proporciona la integración completa de auditoría automática en 5 servicios críticos:
- `reservation_service.py` - crear, actualizar, cancelar reservas
- `payment_service.py` - procesar pagos, depósitos, reembolsos
- `checkin_service.py` - check-in/check-out de huéspedes
- `guest_service.py` - crear/actualizar perfil de huéspedes
- `hotel_service.py` - configuración de hotel, membresías

**Importes necesarios:**

```python
from app.decorators.audit_hooks import AuditContext, audited_change, _entity_to_dict
from app.models.audit import ActionCodeEnum, EntityTypeEnum, SourceCodeEnum
```

---

## 1. RESERVATION_SERVICE.PY

### A. Crear reserva (CREATE)

**Ubicación:** Función `create_reservation()` o donde se inserta la nueva Reservation

**Código para insertar DESPUÉS de `db.add(reservation)` y `db.flush()`:**

```python
def create_reservation(db: Session, data: ReservationCreate, hotel_id: int, user_id: int) -> Reservation:
    """
    Create a new reservation with automatic audit logging.
    """
    # ... existing logic to build reservation ...
    
    reservation = Reservation(
        hotel_id=hotel_id,
        guest_id=guest.id,
        room_id=room.id,
        check_in=data.check_in,
        check_out=data.check_out,
        status=ReservationStatusEnum.DRAFT,
        confirmation_code=generate_confirmation_code(),
        # ... other fields ...
    )
    
    db.add(reservation)
    db.flush()  # Ensure reservation has ID
    
    # AUDIT HOOK: Record reservation creation
    from app.decorators.audit_hooks import AuditContext
    audit = AuditContext(db, user_id, hotel_id)
    audit.record(
        entity_type=EntityTypeEnum.RESERVATION,
        action=ActionCodeEnum.CREATE,
        entity_id=reservation.id,
        after=_entity_to_dict(reservation),
        change_summary=f"Reservation {reservation.confirmation_code} created for guest {guest.email}",
        source_code=SourceCodeEnum.API,
    )
    
    return reservation
```

### B. Actualizar reserva (UPDATE)

**Ubicación:** Función `update_reservation()` o donde se modifica Reservation

**Código para insertar ANTES de `db.flush()` después de hacer cambios:**

```python
def update_reservation(db: Session, reservation_id: int, data: ReservationUpdate, user_id: int) -> Reservation:
    """
    Update reservation with before/after audit snapshots.
    """
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise ReservationError(f"Reservation {reservation_id} not found")
    
    # Capture BEFORE state
    before_state = _entity_to_dict(reservation)
    
    # Apply updates
    if data.check_in:
        reservation.check_in = data.check_in
    if data.check_out:
        reservation.check_out = data.check_out
    if data.notes:
        reservation.notes = data.notes
    # ... other field updates ...
    
    db.flush()
    
    # Capture AFTER state
    after_state = _entity_to_dict(reservation)
    
    # AUDIT HOOK: Record update
    audit = AuditContext(db, user_id, reservation.hotel_id)
    audit.record(
        entity_type=EntityTypeEnum.RESERVATION,
        action=ActionCodeEnum.UPDATE,
        entity_id=reservation.id,
        before=before_state,
        after=after_state,
        change_summary=f"Reservation {reservation.confirmation_code} updated",
        source_code=SourceCodeEnum.API,
    )
    
    return reservation
```

### C. Cancelar reserva (CANCEL)

**Ubicación:** Función `cancel_reservation()` o similar

**Código para insertar ANTES de cambiar el status:**

```python
def cancel_reservation(db: Session, reservation_id: int, reason: str, user_id: int) -> Reservation:
    """
    Cancel reservation with audit trail.
    """
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    if not reservation:
        raise ReservationError(f"Reservation {reservation_id} not found")
    
    before_state = _entity_to_dict(reservation)
    
    # Perform cancellation
    old_status = reservation.status
    reservation.status = ReservationStatusEnum.CANCELLED
    reservation.cancelled_at = datetime.now(timezone.utc)
    
    db.flush()
    
    after_state = _entity_to_dict(reservation)
    
    # AUDIT HOOK: Record cancellation
    audit = AuditContext(db, user_id, reservation.hotel_id)
    audit.record(
        entity_type=EntityTypeEnum.RESERVATION,
        action=ActionCodeEnum.CANCEL,
        entity_id=reservation.id,
        before=before_state,
        after=after_state,
        change_summary=f"Reservation {reservation.confirmation_code} cancelled. Reason: {reason}",
        source_code=SourceCodeEnum.API,
        reason_code=reason,
    )
    
    return reservation
```

---

## 2. PAYMENT_SERVICE.PY

### A. Procesar depósito (UPDATE - payment transaction)

**Ubicación:** Función `process_deposit_payment()` o similar

**Código para insertar DESPUÉS de crear Transaction y antes de cambiar Reservation status:**

```python
def process_deposit_payment(
    db: Session,
    reservation_id: int,
    method: PaymentMethodEnum,
    amount: float,
    user_id: int,
    gateway_response: Optional[dict] = None,
) -> Transaction:
    """
    Process deposit payment with audit trail for transaction + reservation.
    """
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    
    # Capture reservation BEFORE
    res_before = _entity_to_dict(reservation)
    
    # Create transaction
    tx = Transaction(
        hotel_id=reservation.hotel_id,
        reservation_id=reservation_id,
        amount=amount,
        currency=reservation.currency_code,
        method=method,
        status=TransactionStatusEnum.COMPLETED,
        type=TransactionTypeEnum.DEPOSIT,
        gateway_response=json.dumps(gateway_response) if gateway_response else None,
    )
    db.add(tx)
    db.flush()
    
    # AUDIT HOOK: Record transaction creation
    audit = AuditContext(db, user_id, reservation.hotel_id)
    audit.record(
        entity_type=EntityTypeEnum.PAYMENT_TRANSACTION,  # If you have this entity type
        action=ActionCodeEnum.CREATE,
        entity_id=tx.id,
        after=_entity_to_dict(tx),
        change_summary=f"Deposit payment {amount} {reservation.currency_code} processed via {method.value}",
        source_code=SourceCodeEnum.API,
    )
    
    # Transition reservation status
    transition_reservation_status(db, reservation, ReservationStatusEnum.DEPOSIT_PAID, user_id)
    
    # Capture reservation AFTER
    res_after = _entity_to_dict(reservation)
    
    # AUDIT HOOK: Record reservation status change
    audit.record(
        entity_type=EntityTypeEnum.RESERVATION,
        action=ActionCodeEnum.UPDATE,
        entity_id=reservation.id,
        before=res_before,
        after=res_after,
        change_summary=f"Reservation status changed to DEPOSIT_PAID",
        source_code=SourceCodeEnum.API,
    )
    
    return tx
```

### B. Procesar pago completo (UPDATE - full payment)

**Ubicación:** Función `process_full_payment()` o similar

**Código:**

```python
def process_full_payment(
    db: Session,
    reservation_id: int,
    method: PaymentMethodEnum,
    amount: float,
    user_id: int,
) -> Transaction:
    """
    Process full payment (balance remaining after deposit).
    """
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    
    res_before = _entity_to_dict(reservation)
    
    # Create balance transaction
    tx = Transaction(
        hotel_id=reservation.hotel_id,
        reservation_id=reservation_id,
        amount=amount,
        currency=reservation.currency_code,
        method=method,
        status=TransactionStatusEnum.COMPLETED,
        type=TransactionTypeEnum.BALANCE,
    )
    db.add(tx)
    db.flush()
    
    # Transition reservation
    transition_reservation_status(db, reservation, ReservationStatusEnum.FULLY_PAID, user_id)
    
    res_after = _entity_to_dict(reservation)
    
    # AUDIT HOOKS
    audit = AuditContext(db, user_id, reservation.hotel_id)
    
    # Log transaction
    audit.record(
        entity_type=EntityTypeEnum.PAYMENT_TRANSACTION,
        action=ActionCodeEnum.CREATE,
        entity_id=tx.id,
        after=_entity_to_dict(tx),
        change_summary=f"Full payment {amount} {reservation.currency_code} processed",
        source_code=SourceCodeEnum.API,
    )
    
    # Log reservation status change
    audit.record(
        entity_type=EntityTypeEnum.RESERVATION,
        action=ActionCodeEnum.UPDATE,
        entity_id=reservation.id,
        before=res_before,
        after=res_after,
        change_summary=f"Reservation fully paid",
        source_code=SourceCodeEnum.API,
    )
    
    return tx
```

### C. Procesar reembolso (REFUND)

**Ubicación:** Función `process_refund()` o similar

**Código:**

```python
def process_refund(
    db: Session,
    reservation_id: int,
    amount: float,
    reason: str,
    user_id: int,
) -> Transaction:
    """
    Process refund with full audit trail.
    """
    reservation = db.query(Reservation).filter(Reservation.id == reservation_id).first()
    
    res_before = _entity_to_dict(reservation)
    
    # Create refund transaction
    tx = Transaction(
        hotel_id=reservation.hotel_id,
        reservation_id=reservation_id,
        amount=-amount,  # Negative for refund
        currency=reservation.currency_code,
        status=TransactionStatusEnum.COMPLETED,
        type=TransactionTypeEnum.REFUND,
        notes=reason,
    )
    db.add(tx)
    db.flush()
    
    # Update reservation
    reservation.status = ReservationStatusEnum.REFUNDED
    db.flush()
    
    res_after = _entity_to_dict(reservation)
    
    # AUDIT HOOKS
    audit = AuditContext(db, user_id, reservation.hotel_id)
    
    audit.record(
        entity_type=EntityTypeEnum.PAYMENT_TRANSACTION,
        action=ActionCodeEnum.CREATE,
        entity_id=tx.id,
        after=_entity_to_dict(tx),
        change_summary=f"Refund {amount} {reservation.currency_code} issued. Reason: {reason}",
        source_code=SourceCodeEnum.API,
        reason_code=reason,
    )
    
    audit.record(
        entity_type=EntityTypeEnum.RESERVATION,
        action=ActionCodeEnum.UPDATE,
        entity_id=reservation.id,
        before=res_before,
        after=res_after,
        change_summary=f"Reservation refunded: {reason}",
        source_code=SourceCodeEnum.API,
        reason_code=reason,
    )
    
    return tx
```

---

## 3. CHECKIN_SERVICE.PY

### A. Perform check-in (UPDATE - status transition)

**Ubicación:** Función `perform_checkin()`

**Código para insertar DESPUÉS de validaciones y ANTES de cambiar status:**

```python
def perform_checkin(db: Session, reservation_id: int, hotel_id: int | None = None) -> Reservation:
    """
    Full check-in process with audit trail.
    """
    reservation_q = db.query(Reservation).filter(Reservation.id == reservation_id)
    if hotel_id is not None:
        reservation_q = reservation_q.filter(Reservation.hotel_id == hotel_id)
    reservation = reservation_q.first()
    
    if not reservation:
        raise CheckInError("Reservation not found")
    
    # Validate before status change
    if reservation.status != ReservationStatusEnum.FULLY_PAID:
        raise CheckInError("Reservation must be fully paid before check-in")
    
    guest = db.query(Guest).filter(Guest.id == reservation.guest_id).first()
    validate_guest_for_checkin(db, guest, reservation.hotel_id, reservation)
    
    # Capture BEFORE state
    res_before = _entity_to_dict(reservation)
    guest_before = _entity_to_dict(guest)
    
    # Perform check-in
    reservation.status = ReservationStatusEnum.CHECKED_IN
    reservation.actual_check_in_at = datetime.now(timezone.utc)
    
    # Mark room as occupied
    room = db.query(Room).filter(Room.id == reservation.room_id).first()
    if room:
        room.status = RoomStatusEnum.OCCUPIED
    
    db.flush()
    
    # Capture AFTER state
    res_after = _entity_to_dict(reservation)
    room_after = _entity_to_dict(room) if room else None
    
    # AUDIT HOOKS
    audit = AuditContext(db, user_id, reservation.hotel_id)  # user_id from context/request
    
    # Log reservation check-in
    audit.record(
        entity_type=EntityTypeEnum.RESERVATION,
        action=ActionCodeEnum.UPDATE,
        entity_id=reservation.id,
        before=res_before,
        after=res_after,
        change_summary=f"Guest {guest.first_name} {guest.last_name} checked in to room {room.number if room else 'N/A'}",
        source_code=SourceCodeEnum.MANUAL,
    )
    
    # Log room status change
    if room and room_after:
        audit.record(
            entity_type=EntityTypeEnum.ROOM,
            action=ActionCodeEnum.UPDATE,
            entity_id=room.id,
            before={"status": RoomStatusEnum.AVAILABLE},
            after=room_after,
            change_summary=f"Room marked as occupied (check-in)",
            source_code=SourceCodeEnum.SYSTEM,
        )
    
    return reservation
```

### B. Perform check-out (UPDATE - status transition)

**Ubicación:** Función `perform_checkout()` (si existe)

**Código:**

```python
def perform_checkout(db: Session, reservation_id: int, user_id: int, hotel_id: int | None = None) -> Reservation:
    """
    Check-out process with audit trail.
    """
    reservation_q = db.query(Reservation).filter(Reservation.id == reservation_id)
    if hotel_id is not None:
        reservation_q = reservation_q.filter(Reservation.hotel_id == hotel_id)
    reservation = reservation_q.first()
    
    if not reservation:
        raise CheckInError("Reservation not found")
    
    # Capture BEFORE state
    res_before = _entity_to_dict(reservation)
    room_before = None
    
    room = db.query(Room).filter(Room.id == reservation.room_id).first()
    if room:
        room_before = _entity_to_dict(room)
    
    # Perform check-out
    reservation.status = ReservationStatusEnum.CHECKED_OUT
    reservation.actual_check_out_at = datetime.now(timezone.utc)
    
    if room:
        room.status = RoomStatusEnum.AVAILABLE
    
    db.flush()
    
    # Capture AFTER state
    res_after = _entity_to_dict(reservation)
    room_after = _entity_to_dict(room) if room else None
    
    # AUDIT HOOKS
    audit = AuditContext(db, user_id, reservation.hotel_id)
    
    audit.record(
        entity_type=EntityTypeEnum.RESERVATION,
        action=ActionCodeEnum.UPDATE,
        entity_id=reservation.id,
        before=res_before,
        after=res_after,
        change_summary=f"Guest checked out from room {room.number if room else 'N/A'}",
        source_code=SourceCodeEnum.MANUAL,
    )
    
    if room and room_after:
        audit.record(
            entity_type=EntityTypeEnum.ROOM,
            action=ActionCodeEnum.UPDATE,
            entity_id=room.id,
            before=room_before,
            after=room_after,
            change_summary=f"Room marked as available (check-out)",
            source_code=SourceCodeEnum.SYSTEM,
        )
    
    return reservation
```

---

## 4. GUEST_SERVICE.PY (or similar)

### A. Crear huésped (CREATE)

**Ubicación:** Función `create_guest()` o en el endpoint POST

**Código:**

```python
def create_guest(db: Session, data: GuestCreate, hotel_id: int, user_id: int) -> Guest:
    """
    Create guest profile with audit trail.
    """
    guest = Guest(
        hotel_id=hotel_id,
        first_name=data.first_name,
        last_name=data.last_name,
        email=data.email,
        phone=data.phone,
        document_type=data.document_type,
        document_number=data.document_number,
        birthdate=data.birthdate,
        nationality=data.nationality,
        # ... other fields ...
    )
    
    db.add(guest)
    db.flush()
    
    # AUDIT HOOK
    audit = AuditContext(db, user_id, hotel_id)
    audit.record(
        entity_type=EntityTypeEnum.GUEST,
        action=ActionCodeEnum.CREATE,
        entity_id=guest.id,
        after=_entity_to_dict(guest),
        change_summary=f"Guest profile created: {guest.first_name} {guest.last_name}",
        source_code=SourceCodeEnum.API,
    )
    
    return guest
```

### B. Actualizar perfil de huésped (UPDATE)

**Ubicación:** Función `update_guest()` o PATCH endpoint

**Código:**

```python
def update_guest(db: Session, guest_id: int, data: GuestUpdate, user_id: int) -> Guest:
    """
    Update guest profile with before/after audit snapshots.
    """
    guest = db.query(Guest).filter(Guest.id == guest_id).first()
    if not guest:
        raise GuestError(f"Guest {guest_id} not found")
    
    before_state = _entity_to_dict(guest)
    
    # Apply updates
    if data.first_name:
        guest.first_name = data.first_name
    if data.last_name:
        guest.last_name = data.last_name
    if data.email:
        guest.email = data.email
    if data.phone:
        guest.phone = data.phone
    if data.document_number:
        guest.document_number = data.document_number
    # ... other field updates ...
    
    db.flush()
    
    after_state = _entity_to_dict(guest)
    
    # AUDIT HOOK
    audit = AuditContext(db, user_id, guest.hotel_id)
    audit.record(
        entity_type=EntityTypeEnum.GUEST,
        action=ActionCodeEnum.UPDATE,
        entity_id=guest.id,
        before=before_state,
        after=after_state,
        change_summary=f"Guest profile updated: {guest.first_name} {guest.last_name}",
        source_code=SourceCodeEnum.API,
    )
    
    return guest
```

---

## 5. HOTEL_SERVICE.PY

### A. Actualizar configuración de hotel (UPDATE)

**Ubicación:** Función que modifique HotelConfiguration

**Código:**

```python
def update_hotel_config(
    db: Session,
    hotel_id: int,
    data: HotelConfigUpdate,
    user_id: int,
) -> HotelConfiguration:
    """
    Update hotel configuration with audit trail.
    """
    config = db.query(HotelConfiguration).filter(HotelConfiguration.id == hotel_id).first()
    if not config:
        raise HotelError(f"Hotel {hotel_id} not found")
    
    before_state = _entity_to_dict(config)
    
    # Apply updates
    if data.hotel_name:
        config.hotel_name = data.hotel_name
    if data.check_in_time:
        config.check_in_time = data.check_in_time
    if data.check_out_time:
        config.check_out_time = data.check_out_time
    if data.deposit_percentage is not None:
        config.deposit_percentage = data.deposit_percentage
    if data.enable_cash is not None:
        config.enable_cash = data.enable_cash
    if data.enable_mercado_pago is not None:
        config.enable_mercado_pago = data.enable_mercado_pago
    # ... other config updates ...
    
    db.flush()
    
    after_state = _entity_to_dict(config)
    
    # AUDIT HOOK
    audit = AuditContext(db, user_id, hotel_id)
    audit.record(
        entity_type=EntityTypeEnum.HOTEL_CONFIGURATION,
        action=ActionCodeEnum.UPDATE,
        entity_id=hotel_id,
        before=before_state,
        after=after_state,
        change_summary=f"Hotel configuration updated",
        source_code=SourceCodeEnum.MANUAL,
    )
    
    return config
```

### B. Crear membresía de usuario (CREATE)

**Ubicación:** Función que cree HotelMembership

**Código:**

```python
def add_user_to_hotel(
    db: Session,
    hotel_id: int,
    user_id: int,
    role: str,
    created_by_user_id: int,
) -> HotelMembership:
    """
    Add user to hotel with role, with audit trail.
    """
    # Check if already member
    existing = db.query(HotelMembership).filter(
        HotelMembership.hotel_id == hotel_id,
        HotelMembership.user_id == user_id,
    ).first()
    if existing:
        raise HotelError(f"User already member of this hotel")
    
    membership = HotelMembership(
        hotel_id=hotel_id,
        user_id=user_id,
        role=role,
        status="active",
    )
    
    db.add(membership)
    db.flush()
    
    # Get user name for summary
    user = db.query(User).filter(User.id == user_id).first()
    user_name = f"{user.first_name} {user.last_name}" if user else f"User {user_id}"
    
    # AUDIT HOOK
    audit = AuditContext(db, created_by_user_id, hotel_id)
    audit.record(
        entity_type=EntityTypeEnum.HOTEL_MEMBERSHIP,
        action=ActionCodeEnum.CREATE,
        entity_id=membership.id,
        after=_entity_to_dict(membership),
        change_summary=f"User {user_name} added to hotel with role '{role}'",
        source_code=SourceCodeEnum.MANUAL,
    )
    
    return membership
```

---

## Guía de Implementación

### Paso 1: Crear archivo de decoradores
Copiar `/app/decorators/audit_hooks.py` al proyecto.

### Paso 2: Agregar imports en cada servicio

```python
from app.decorators.audit_hooks import AuditContext, _entity_to_dict
from app.models.audit import ActionCodeEnum, EntityTypeEnum, SourceCodeEnum
```

### Paso 3: Integrar en métodos de escritura

Para cada método que cree/actualice/elimine:
1. Capturar estado ANTES (si UPDATE): `before = _entity_to_dict(entity)`
2. Ejecutar operación
3. Capturar estado DESPUÉS: `after = _entity_to_dict(entity)`
4. Crear `AuditContext(db, user_id, hotel_id)`
5. Llamar `audit.record(...)`

### Paso 4: Validación

Ejecutar tests para verificar que:
- Audit logs se crean en base de datos
- Before/after snapshots son correctos
- No hay cambios en la lógica principal (solo agregar audit después)
- Falla de audit no afecta la operación principal (wrapped en try/except)

---

## Contexto de Usuario

Para obtener `user_id` en los servicios, típicamente proviene de:

1. **Request context (FastAPI):**
   ```python
   from fastapi import Request
   
   request: Request
   user_id = request.state.user_id  # Asume middleware que lo setea
   ```

2. **Token JWT:**
   ```python
   from app.utils.jwt_utils import decode_token
   
   token = extract_token_from_request(request)
   payload = decode_token(token)
   user_id = payload.get("user_id")
   ```

3. **Parámetro explícito:**
   ```python
   def create_reservation(db, data, hotel_id, user_id):  # user_id como param
       ...
   ```

---

## Enums disponibles

Ver `app/models/audit.py`:

### ActionCodeEnum
- `CREATE` - Nueva entidad
- `UPDATE` - Modificación
- `DELETE` - Eliminación
- `CANCEL` - Cancelación (reservas)
- `APPROVE` - Aprobación
- `REJECT` - Rechazo
- `REVERT` - Deshacer
- `RESTORE` - Restaurar
- `MERGE` - Fusionar
- `SPLIT` - Dividir

### EntityTypeEnum
- `RESERVATION`, `GUEST`, `ROOM`, `ROOM_CATEGORY`
- `RATE_PLAN`, `RATE_PLAN_PRICE`, `SELLABLE_PRODUCT`, `TAX_POLICY`
- `OTA_CONNECTION`, `OTA_PROPERTY_MAPPING`, `OTA_RESERVATION_LINK`
- `HOTEL_CONFIGURATION`, `HOTEL_MEMBERSHIP`, `USER`, `SECURITY_TOKEN`
- `RESERVATION_ADJUSTMENT`, `ROOM_MOVE_EVENT`, `BILLING_ADJUSTMENT`

### SourceCodeEnum
- `API` - HTTP request
- `OTA_SYNC` - Sincronización automática
- `MANUAL` - Interfaz de usuario
- `SYSTEM` - Auto-triggered
- `ADMIN_BULK` - Operación batch
- `IMPORT` - Data import
- `WEBHOOK` - Inbound webhook

---

## Mejores prácticas

1. **Always capture BEFORE before making changes**
   ```python
   before = _entity_to_dict(entity)
   entity.field = new_value
   db.flush()
   after = _entity_to_dict(entity)
   ```

2. **Use descriptive change_summary**
   ```python
   # Good
   change_summary=f"Reservation {res.confirmation_code} cancelled by user due to {reason}"
   
   # Bad
   change_summary="Updated"
   ```

3. **Set source_code correctly**
   ```python
   source_code=SourceCodeEnum.API      # API call
   source_code=SourceCodeEnum.OTA_SYNC # Auto-sync
   source_code=SourceCodeEnum.MANUAL   # UI action
   source_code=SourceCodeEnum.SYSTEM   # Background job
   ```

4. **Don't let audit failure break main operation**
   - Already handled in `AuditContext.record()` (wrapped in try/except)
   - Logs error but doesn't re-raise

5. **Use entity_id for linking**
   ```python
   # ID must match entity_type
   entity_type=EntityTypeEnum.RESERVATION,
   entity_id=reservation.id,  # Not guest.id
   ```

---

## Testing

Ejemplo de test:

```python
def test_reservation_creation_audited(db: Session):
    """Verify audit log is created when reservation is made."""
    user_id = 1
    hotel_id = 1
    
    reservation = create_reservation(
        db,
        data=ReservationCreate(...),
        hotel_id=hotel_id,
        user_id=user_id,
    )
    
    # Query audit log
    audit_event = db.query(HotelAuditEvent).filter(
        HotelAuditEvent.entity_type == EntityTypeEnum.RESERVATION,
        HotelAuditEvent.entity_id == reservation.id,
        HotelAuditEvent.action_code == ActionCodeEnum.CREATE,
    ).first()
    
    assert audit_event is not None
    assert audit_event.user_id == user_id
    assert audit_event.hotel_id == hotel_id
    assert audit_event.after_json is not None
    
    after_data = json.loads(audit_event.after_json)
    assert after_data["confirmation_code"] == reservation.confirmation_code
```
