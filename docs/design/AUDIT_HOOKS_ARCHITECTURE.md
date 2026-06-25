# Audit Hooks - Arquitectura

## Diagrama de Flujo

```
┌─────────────────────────────────────────────────────────────────────────┐
│                        SERVICE LAYER (e.g., ReservationService)         │
├─────────────────────────────────────────────────────────────────────────┤
│                                                                           │
│  def create_reservation(db, data, hotel_id, user_id):                   │
│      ┌─────────────────────────────────────────────┐                    │
│      │ 1. Capture BEFORE state                     │                    │
│      │    before = _entity_to_dict(entity)         │                    │
│      └──────────────────┬──────────────────────────┘                    │
│                         │                                                │
│      ┌──────────────────▼──────────────────────────┐                    │
│      │ 2. Execute Business Logic                  │                    │
│      │    entity.field = new_value                │                    │
│      │    db.add(entity)                          │                    │
│      │    db.flush()                              │                    │
│      └──────────────────┬──────────────────────────┘                    │
│                         │                                                │
│      ┌──────────────────▼──────────────────────────┐                    │
│      │ 3. Capture AFTER state                      │                    │
│      │    after = _entity_to_dict(entity)          │                    │
│      └──────────────────┬──────────────────────────┘                    │
│                         │                                                │
│      ┌──────────────────▼──────────────────────────┐                    │
│      │ 4. Record Audit Entry                       │                    │
│      │    audit = AuditContext(db, user_id, ..)   │                    │
│      │    audit.record(                           │                    │
│      │      entity_type=EntityTypeEnum.GUEST,     │                    │
│      │      action=ActionCodeEnum.CREATE,         │                    │
│      │      before=before,                        │                    │
│      │      after=after,                          │                    │
│      │      ...                                   │                    │
│      │    )                                        │                    │
│      └──────────────────┬──────────────────────────┘                    │
│                         │                                                │
│      ┌──────────────────▼──────────────────────────┐                    │
│      │ 5. Commit Changes                           │                    │
│      │    db.commit()                              │                    │
│      └──────────────────┬──────────────────────────┘                    │
│                         │                                                │
│      ┌──────────────────▼──────────────────────────┐                    │
│      │ 6. Return Result                            │                    │
│      │    return entity                            │                    │
│      └──────────────────────────────────────────────┘                    │
│                                                                           │
└─────────────────────────────────────────────────────────────────────────┘
                              │
                              │ db session with changes
                              │
         ┌────────────────────▼───────────────────────┐
         │                                             │
         ▼                                             ▼
    ┌──────────────────┐                  ┌──────────────────┐
    │ audit_hooks.py   │                  │ audit_service.py │
    ├──────────────────┤                  ├──────────────────┤
    │ • AuditContext   │──┬───────┬──────▶│ • record_change()│
    │ • _entity_to_dict│  │       │       │ • get timeline   │
    │ • @audited_change│  │       │       │ • get activity   │
    └──────────────────┘  │       │       └──────────────────┘
                          │       │              │
                          │       │              │
                    ┌─────▼───────▼──────┐       │
                    │  Insert into DB    │       │
                    │  (hotel_audit_event)       │
                    └─────────────────────┘       │
                                                  │
                    ┌─────────────────────┐       │
                    │  Extract field      │◀─────┘
                    │  changes and insert │
                    │  (audit_log_entry)  │
                    └─────────────────────┘
```

---

## Diagrama de Componentes

```
┌──────────────────────────────────────────────────────────────────┐
│                      HOTEL CHIPRE PMS                             │
├──────────────────────────────────────────────────────────────────┤
│                                                                   │
│ ┌────────────────────────┐         ┌─────────────────────────┐  │
│ │   SERVICE LAYER        │         │  AUDIT SYSTEM           │  │
│ ├────────────────────────┤         ├─────────────────────────┤  │
│ │                        │         │                         │  │
│ │ • reservation_service  │         │ app/decorators/         │  │
│ │ • payment_service      │         │ └─ audit_hooks.py       │  │
│ │ • checkin_service      │         │                         │  │
│ │ • guest_service        │    ┌────┼─ AuditContext          │  │
│ │ • hotel_service        │    │    │                         │  │
│ │                        │    │    │ app/services/           │  │
│ └────────────┬───────────┘    │    │ └─ audit_service.py     │  │
│              │                │    └─────────────────────────┘  │
│              │ calls          │                                  │
│              └────────────────┼──────┐                           │
│                               │      │                           │
│ ┌────────────────────────┐    │      │                           │
│ │   ORM MODELS           │    │      │                           │
│ ├────────────────────────┤    │      │                           │
│ │                        │    │      │                           │
│ │ app/models/            │◀───┘      │                           │
│ │ ├─ reservation.py      │           │                           │
│ │ ├─ guest.py            │           │                           │
│ │ ├─ room.py             │           │                           │
│ │ ├─ transaction.py      │           │                           │
│ │ └─ audit.py            │◀──────────┘                           │
│ │                        │                                       │
│ └────────────┬───────────┘                                       │
│              │                                                    │
│              │ SQLAlchemy                                        │
│              ▼                                                    │
│ ┌────────────────────────────────┐                               │
│ │  DATABASE (PostgreSQL/SQLite)  │                               │
│ ├────────────────────────────────┤                               │
│ │                                │                               │
│ │ Tables:                        │                               │
│ │ • reservation                  │                               │
│ │ • guest                        │                               │
│ │ • room                         │                               │
│ │ • transaction                  │                               │
│ │ ├─ hotel_audit_event          │   ◀─── Main audit log        │
│ │ └─ audit_log_entry            │   ◀─── Field-level changes   │
│ │                                │                               │
│ └────────────────────────────────┘                               │
│                                                                   │
└──────────────────────────────────────────────────────────────────┘
```

---

## Tabla de Datos

### hotel_audit_event

```
┌───────────────────────────────────────────────────────────────┐
│ Column             │ Type      │ Purpose                        │
├───────────────────────────────────────────────────────────────┤
│ id                 │ INT (PK)  │ Unique audit event ID          │
│ hotel_id           │ INT (FK)  │ Which hotel                    │
│ user_id            │ INT (FK)  │ Who made the change            │
│ entity_type        │ ENUM      │ What type (RESERVATION, etc)   │
│ entity_id          │ INT       │ Which entity (res_id, etc)     │
│ action_code        │ ENUM      │ What action (CREATE, UPDATE)   │
│ before_json        │ JSON      │ State before change            │
│ after_json         │ JSON      │ State after change             │
│ change_summary     │ STRING    │ Human description              │
│ source_code        │ ENUM      │ Where from (API, MANUAL, etc)  │
│ reason_code        │ STRING    │ Why (for DELETE/CANCEL)        │
│ ip_address         │ STRING    │ Client IP (optional)           │
│ request_id         │ UUID      │ Request correlation ID         │
│ created_at         │ DATETIME  │ When it happened               │
└───────────────────────────────────────────────────────────────┘

Example rows:
┌─────┬──────────┬────────┬──────────────┬───────────┬────────────┬─────────────────┐
│ id  │ hotel_id │ user_id│ entity_type  │ entity_id │ action_code│ change_summary  │
├─────┼──────────┼────────┼──────────────┼───────────┼────────────┼─────────────────┤
│ 1   │ 1        │ 5      │ reservation  │ 123       │ create     │ Res created...  │
│ 2   │ 1        │ 5      │ reservation  │ 123       │ update     │ Res updated...  │
│ 3   │ 1        │ 7      │ guest        │ 45        │ create     │ Guest created.. │
│ 4   │ 1        │ 6      │ transaction  │ 890       │ create     │ Payment proc... │
└─────┴──────────┴────────┴──────────────┴───────────┴────────────┴─────────────────┘
```

### audit_log_entry

```
┌──────────────────────────────────────────────────────────┐
│ Column                │ Type      │ Purpose               │
├──────────────────────────────────────────────────────────┤
│ id                    │ INT (PK)  │ Unique entry ID       │
│ hotel_audit_event_id  │ INT (FK)  │ Link to event         │
│ hotel_id              │ INT (FK)  │ Which hotel           │
│ field_name            │ STRING    │ Field that changed    │
│ data_type             │ ENUM      │ Type (INT, STRING)    │
│ old_value             │ STRING    │ Previous value        │
│ new_value             │ STRING    │ New value             │
│ was_null              │ BOOLEAN   │ Was old NULL?         │
│ is_null               │ BOOLEAN   │ Is new NULL?          │
└──────────────────────────────────────────────────────────┘

Example rows:
┌─────┬──────────────────┬──────────┬─────────────┬──────────┬──────────┐
│ id  │ event_id         │ field    │ old_value   │ new_value│ data_type│
├─────┼──────────────────┼──────────┼─────────────┼──────────┼──────────┤
│ 1   │ 2                │ status   │ draft       │ confirmed│ STRING   │
│ 2   │ 2                │ total_amt│ 500.00      │ 550.00   │ FLOAT    │
│ 3   │ 3                │ email    │ NULL        │ john@... │ STRING   │
└─────┴──────────────────┴──────────┴─────────────┴──────────┴──────────┘
```

---

## Flujo de Integración en Servicios

```
┌─────────────────────────────────────────────────────────────────┐
│  STEP 1: Add imports at top of service file                     │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  from app.decorators.audit_hooks import AuditContext, ...       │
│  from app.models.audit import ActionCodeEnum, EntityTypeEnum... │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 2: In write method, capture BEFORE state                  │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  def create_reservation(...):                                   │
│      # BEFORE capture                                           │
│      before = _entity_to_dict(reservation)  # Line 1            │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 3: Execute business logic                                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│      # Business logic                                           │
│      reservation.field = value                                  │
│      db.add(reservation)                                        │
│      db.flush()  # Important!                                   │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 4: Capture AFTER state and record audit                   │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│      # AFTER capture                                            │
│      after = _entity_to_dict(reservation)   # Line 2            │
│                                                                  │
│      # Record audit                                             │
│      audit = AuditContext(db, user_id, hotel_id)                │
│      audit.record(                                              │
│          entity_type=EntityTypeEnum.RESERVATION,                │
│          action=ActionCodeEnum.CREATE,                          │
│          entity_id=reservation.id,                              │
│          after=after,                                           │
│          change_summary=f"Res {res.confirmation_code} created", │
│      )                                                          │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│  STEP 5: Commit changes                                         │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│      db.commit()  # Both audit and data committed               │
│      return reservation                                         │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
```

---

## Error Handling Flow

```
┌──────────────────────────┐
│ audit.record(...)        │
└─────────────┬────────────┘
              │
    ┌─────────▼──────────┐
    │  Try block         │
    │  ├─ Extract context│
    │  ├─ Call DB ops   │
    │  └─ Create event  │
    └─────────┬──────────┘
              │
      ┌───────┴────────┐
      │                │
      ▼ Success        ▼ Error
   ┌──────┐         ┌──────────┐
   │ Log  │         │ Log error│
   │ event│         │ (WARNING)│
   │ done │         │ Continue │
   └──────┘         │ execution│
                    └──────────┘

KEY: Audit failure NEVER breaks main operation
     - Try/except wraps all audit code
     - Errors are logged but not re-raised
     - Main service logic continues normally
```

---

## Integration Points

```
Services that need audit integration:

┌──────────────────────────────────┐
│ reservation_service.py           │
├──────────────────────────────────┤
│ • create_reservation()      [*]  │  [*] = requires audit
│ • update_reservation()      [*]  │
│ • cancel_reservation()      [*]  │
│ • transition_status()       [*]  │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│ payment_service.py               │
├──────────────────────────────────┤
│ • process_deposit_payment() [*]  │
│ • process_full_payment()    [*]  │
│ • process_refund()          [*]  │
│ • create_transaction()      [*]  │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│ checkin_service.py               │
├──────────────────────────────────┤
│ • perform_checkin()         [*]  │
│ • perform_checkout()        [*]  │
│ • validate_guest()          [-]  │  [-] = read-only, no audit
└──────────────────────────────────┘

┌──────────────────────────────────┐
│ guest_service.py                 │
├──────────────────────────────────┤
│ • create_guest()            [*]  │
│ • update_guest()            [*]  │
│ • validate_guest_data()     [-]  │
└──────────────────────────────────┘

┌──────────────────────────────────┐
│ hotel_service.py                 │
├──────────────────────────────────┤
│ • update_hotel_config()     [*]  │
│ • add_user_to_hotel()       [*]  │
│ • remove_user()             [*]  │
│ • get_or_create_hotel()     [*]  │
└──────────────────────────────────┘
```

---

## Data Flow Example

### Create Reservation

```
CREATE RESERVATION
┌────────────────────────────────────────────────────┐
│ 1. Service Layer                                    │
│                                                    │
│ create_reservation(db, data, hotel_id, user_id)   │
│ ├─ Create Reservation object                      │
│ ├─ db.add(reservation)                            │
│ ├─ db.flush()  ◀─ Get ID for audit               │
│ │                                                 │
│ └─ AUDIT RECORDING                               │
│    ├─ before = _entity_to_dict(reservation)       │
│    │  Result: {"id": 123, "status": "draft", ...} │
│    │                                              │
│    ├─ after = _entity_to_dict(reservation)        │
│    │  Result: {"id": 123, "status": "draft", ...} │
│    │  (same, because just created)                │
│    │                                              │
│    └─ audit.record(                               │
│       entity_type=EntityTypeEnum.RESERVATION,     │
│       action=ActionCodeEnum.CREATE,               │
│       entity_id=123,                              │
│       before=None,  (for CREATE, no "before")    │
│       after={...},  (full state)                 │
│       change_summary="..."                        │
│    )                                              │
│                                                   │
│ ├─ db.commit()  ◀─ Persist both data and audit  │
│ └─ return reservation                             │
└────────────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────┐
│ 2. Audit Service                                    │
│                                                    │
│ audit_service.record_change(...)                  │
│ ├─ Create HotelAuditEvent                         │
│ │  ├─ hotel_id=1                                  │
│ │  ├─ user_id=5                                   │
│ │  ├─ entity_type='reservation'                   │
│ │  ├─ entity_id=123                               │
│ │  ├─ action_code='create'                        │
│ │  ├─ after_json='{"id": 123, ...}'               │
│ │  └─ created_at=NOW()                            │
│ │                                                 │
│ └─ Extract field changes                          │
│    ├─ For each field in after_json                │
│    └─ Create AuditLogEntry (if changed)           │
│                                                   │
│ ├─ db.add(event)                                  │
│ ├─ db.add(entries...)                             │
│ └─ db.flush()                                     │
└────────────────────────────────────────────────────┘
                     │
                     ▼
┌────────────────────────────────────────────────────┐
│ 3. Database                                        │
│                                                   │
│ INSERT INTO hotel_audit_event (                   │
│   hotel_id, user_id, entity_type, entity_id,      │
│   action_code, after_json, created_at             │
│ ) VALUES (1, 5, 'reservation', 123, 'create',    │
│   '{"id": 123, ...}', NOW())                      │
│                                                   │
│ ✓ Row inserted into hotel_audit_event             │
│ ✓ N rows inserted into audit_log_entry            │
│ ✓ Main reservation data also inserted             │
└────────────────────────────────────────────────────┘
```

---

## Performance Considerations

```
┌────────────────────────────────┐
│ Audit Impact Per Operation     │
├────────────────────────────────┤
│ • Snapshot capture: <1ms       │
│ • DB insert: ~2-5ms            │
│ • Field extraction: <1ms       │
│ • Total per op: ~3-6ms         │
│ • Async option: Not in v1      │
├────────────────────────────────┤
│ Storage (per audit event)      │
│ • Event record: ~0.5-2KB       │
│ • Field entries: ~0.1-1KB each │
│ • Total typical: ~1-5KB        │
└────────────────────────────────┘

Optimization strategies:
1. Batch inserts (multiple entities in one operation)
2. Selective auditing (only critical entities)
3. Archive old events (retention policy)
4. Index on (hotel_id, created_at, entity_type)
```

---

## Security Considerations

```
┌──────────────────────────────────────────────────┐
│ Audit Trail Immutability                         │
├──────────────────────────────────────────────────┤
│ ✓ Append-only (no UPDATE/DELETE on audit events) │
│ ✓ Timestamps immutable (created_at not changeable)
│ ✓ User tracking (user_id recorded)               │
│ ✓ Source tracking (source_code recorded)         │
│ ✓ IP address logging (optional)                  │
│ ✓ Request correlation (request_id)               │
├──────────────────────────────────────────────────┤
│ Access Control                                   │
├──────────────────────────────────────────────────┤
│ • Audit data readable by: Admin, Auditor roles   │
│ • Audit data writable by: System only (via audit │
│   hooks, no manual INSERT)                       │
│ • Sensitive fields in snapshots: Be selective    │
│   (consider PII redaction)                       │
└──────────────────────────────────────────────────┘
```

---

## Extension Points

```
Future enhancements (not in v1):

1. Webhooks for audit events
   └─ config: AuditWebhook, AuditWebhookEvent

2. Approval workflows with audit
   └─ Track approval chains: request → approve → execute

3. Reversals and rollback
   └─ "Revert to state N" with audit trail

4. Async/batch processing
   └─ Defer audit inserts for bulk operations

5. Encryption of sensitive data
   └─ Encrypt before_json/after_json fields

6. Real-time dashboards
   └─ WebSocket feed of audit events
```

---

**Architecture Version:** 1.0
**Last Updated:** 2026-06-10
