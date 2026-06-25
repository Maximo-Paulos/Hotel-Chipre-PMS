# Audit Log Module - Schema Design

**Date:** 2026-06-09  
**Status:** Design Specification  
**Scope:** Complete audit logging schema for Hotel Chipre PMS

---

## Overview

The audit logging system provides comprehensive change tracking across all major entities in the Hotel Chipre PMS. It captures:
- **Who** made the change (user_id)
- **What** changed (entity type, entity_id, field-level changes)
- **When** it happened (timestamp with timezone)
- **Where** it came from (source: API, OTA, Manual, System)
- **Why** it happened (reason_code, notes)
- **Before/After snapshots** (full JSON state comparison)

---

## Core Tables

### 1. `hotel_audit_events` (Existing - Enhanced)

**Purpose:** Capture all entity changes at the hotel level.

```python
class HotelAuditEvent(Base):
    __tablename__ = "hotel_audit_events"
    
    id: int                          # Primary key
    hotel_id: int                    # Foreign key → hotel_configuration
    user_id: int                     # Foreign key → users (who made change)
    action_code: str(80)             # CREATE | UPDATE | DELETE | CANCEL | APPROVE
    entity_type: str(60)             # "Reservation", "Room", "Guest", "RatePlan", etc.
    entity_id: int (nullable)        # Foreign key to the affected entity
    
    # Change data
    before_json: Text (nullable)     # Previous state (JSON)
    after_json: Text (nullable)      # New state (JSON)
    change_summary: str(255)         # Human-readable summary
    
    # Context
    source_code: str(50)             # "api" | "ota_sync" | "manual" | "system"
    reason_code: str(80)             # "cancellation_guest_request" | etc.
    request_id: str(100) (nullable)  # Correlation ID for related events
    ip_address: str(45) (nullable)   # IPv4/IPv6 for security audit
    
    # Timestamps
    created_at: DateTime(tz)         # UTC timestamp
    
    # Indexes
    Index: (hotel_id, created_at)    # Fast timeline queries
    Index: (hotel_id, action_code)   # Filter by action type
    Index: (entity_type, entity_id)  # Find all changes to entity
    Index: (user_id, created_at)     # User activity tracking
    Index: (request_id)              # Trace multi-step operations
```

---

### 2. `audit_log_entries` (New - Detailed Change Tracking)

**Purpose:** Fine-grained field-level change tracking for complex updates.

```python
class AuditLogEntry(Base):
    __tablename__ = "audit_log_entries"
    
    id: int                               # Primary key
    hotel_audit_event_id: int             # Foreign key → hotel_audit_events
    field_name: str(100)                  # "status" | "room_id" | "total_amount"
    field_path: str(255) (nullable)       # "address.city" for nested fields
    data_type: str(50)                    # "string" | "integer" | "float" | "json" | "enum"
    
    # Values
    old_value: Text (nullable)            # Previous value (string repr)
    new_value: Text (nullable)            # New value (string repr)
    was_null: bool                        # True if field was NULL before
    is_null: bool                         # True if field is NULL after
    
    # Change metadata
    is_system_generated: bool             # True if change auto-computed (e.g., total_amount)
    
    # Timestamps
    created_at: DateTime(tz)
    
    # Indexes
    Index: (hotel_audit_event_id)         # All fields for an event
    Index: (field_name, hotel_id)         # Track changes to specific field
```

---

### 3. `audit_retention_policy` (New - Compliance)

**Purpose:** Configure audit log retention per hotel/entity type.

```python
class AuditRetentionPolicy(Base):
    __tablename__ = "audit_retention_policies"
    
    id: int                              # Primary key
    hotel_id: int                        # Foreign key → hotel_configuration
    entity_type: str(60)                 # "Reservation" or NULL for all
    retention_days: int                  # 365 | 2555 (7 years) | etc.
    archive_after_days: int              # Move to cold storage
    redaction_rules: Text (nullable)     # JSON describing PII redaction
    
    # Status
    is_active: bool                      # Enable/disable
    created_at: DateTime(tz)
    updated_at: DateTime(tz)
    updated_by_user_id: int
    
    # Indexes
    Index: (hotel_id, entity_type)       # Quick policy lookup
    UniqueConstraint: (hotel_id, entity_type)
```

---

### 4. `audit_log_archive` (New - Long-term Storage)

**Purpose:** Store historical audit logs for compliance (read-only in hot DB).

```python
class AuditLogArchive(Base):
    __tablename__ = "audit_log_archives"
    
    id: int                              # Primary key
    hotel_id: int                        # Foreign key → hotel_configuration
    year_month: str(7)                   # "2026-06" for partitioning
    entry_count: int                     # Number of events in archive
    
    # Archive metadata
    archive_format: str(50)              # "json_gzip" | "parquet" | "csv"
    archive_path: str(500)               # S3 path: s3://bucket/hotel_id/2026-06.gz
    archive_size_bytes: int
    checksum_sha256: str(64)
    
    # Lifecycle
    created_at: DateTime(tz)
    verified_at: DateTime(tz) (nullable) # When archive was verified
    locked_at: DateTime(tz)              # When marked immutable
    expires_at: DateTime(tz) (nullable)
    
    # Indexes
    Index: (hotel_id, year_month)        # Find archive for period
    Index: (locked_at, expires_at)       # Find ready-to-delete archives
```

---

### 5. `audit_webhooks` (New - Real-time Alerts)

**Purpose:** Notify integrations of audit-worthy events.

```python
class AuditWebhook(Base):
    __tablename__ = "audit_webhooks"
    
    id: int                              # Primary key
    hotel_id: int                        # Foreign key → hotel_configuration
    name: str(100)                       # "Compliance Lambda" | "SentryAlert"
    webhook_url: str(500)                # HTTPS endpoint
    
    # Filters
    action_codes: str(500)               # CSV: "DELETE,CANCEL" (NULL = all)
    entity_types: str(500)               # CSV: "Reservation,Payment" (NULL = all)
    event_conditions: Text (nullable)    # JSON: {"status_changed_to": "cancelled"}
    
    # Auth
    secret_token: str(255)               # HMAC-SHA256 for payload verification
    headers_json: Text (nullable)        # Custom headers {"X-API-Key": "..."}
    
    # Backoff
    is_active: bool
    max_retries: int                     # Default 3
    retry_delay_seconds: int             # Default 60
    timeout_seconds: int                 # Default 30
    
    # Metadata
    created_at: DateTime(tz)
    updated_at: DateTime(tz)
    last_fired_at: DateTime(tz) (nullable)
    failure_count: int
    
    # Indexes
    Index: (hotel_id, is_active)
```

---

### 6. `audit_webhook_events` (New - Webhook Delivery Tracking)

**Purpose:** Track webhook delivery success/failure.

```python
class AuditWebhookEvent(Base):
    __tablename__ = "audit_webhook_events"
    
    id: int                              # Primary key
    audit_webhook_id: int                # Foreign key → audit_webhooks
    hotel_audit_event_id: int            # Foreign key → hotel_audit_events
    
    # Delivery info
    attempt_number: int                  # 1, 2, 3...
    status: str(50)                      # "pending" | "delivered" | "failed" | "skipped"
    http_status: int (nullable)          # 200, 500, etc.
    
    # Response
    response_body: Text (nullable)       # First 5KB of response
    error_message: str(500) (nullable)
    
    # Timing
    triggered_at: DateTime(tz)
    delivered_at: DateTime(tz) (nullable)
    next_retry_at: DateTime(tz) (nullable)
```

---

## Data Models / Schema Enums

### ActionCodeEnum
```python
class ActionCodeEnum(str, enum.Enum):
    CREATE = "create"              # New entity created
    UPDATE = "update"              # Existing entity modified
    DELETE = "delete"              # Soft/hard delete
    CANCEL = "cancel"              # Cancellation (reservation, etc.)
    APPROVE = "approve"            # Approval workflow
    REJECT = "reject"              # Rejection workflow
    REVERT = "revert"              # Undo previous change
    RESTORE = "restore"            # Restore from archive
    MERGE = "merge"                # Merge two entities
    SPLIT = "split"                # Split entity (e.g., multi-room booking)
```

### SourceCodeEnum
```python
class SourceCodeEnum(str, enum.Enum):
    API = "api"                    # HTTP API call
    OTA_SYNC = "ota_sync"          # Automated OTA synchronization
    MANUAL = "manual"              # Direct UI/form submission
    SYSTEM = "system"              # Auto-triggered (timeout, rule, etc.)
    ADMIN_BULK = "admin_bulk"      # Batch operation
    IMPORT = "import"              # Data import/migration
    WEBHOOK = "webhook"            # Inbound webhook processing
```

### EntityTypeEnum (Supported Entities)
```python
class EntityTypeEnum(str, enum.Enum):
    # Core
    RESERVATION = "reservation"
    GUEST = "guest"
    ROOM = "room"
    ROOM_CATEGORY = "room_category"
    
    # Commercial
    RATE_PLAN = "rate_plan"
    RATE_PLAN_PRICE = "rate_plan_price"
    SELLABLE_PRODUCT = "sellable_product"
    TAX_POLICY = "tax_policy"
    FX_POLICY = "fx_policy"
    
    # OTA
    OTA_CONNECTION = "ota_connection"
    OTA_PROPERTY_MAPPING = "ota_property_mapping"
    OTA_RESERVATION_LINK = "ota_reservation_link"
    
    # Operational
    RESERVATION_ADJUSTMENT = "reservation_adjustment"
    ROOM_MOVE_EVENT = "room_move_event"
    BILLING_ADJUSTMENT = "billing_adjustment"
    
    # Admin
    HOTEL_CONFIGURATION = "hotel_configuration"
    HOTEL_MEMBERSHIP = "hotel_membership"
    USER = "user"
    SECURITY_TOKEN = "security_token"
```

---

## JSON Schema for Snapshots

### Before/After Snapshot Format
```json
{
  "entity_id": 12345,
  "entity_type": "reservation",
  "timestamp": "2026-06-09T14:30:45.123Z",
  "snapshot": {
    "id": 12345,
    "confirmation_code": "CHI-2026-001",
    "guest_id": 789,
    "status": "checked_in",
    "room_id": 42,
    "check_in_date": "2026-06-09",
    "check_out_date": "2026-06-12",
    "total_amount": 450.00,
    "amount_paid": 450.00,
    "currency_code": "ARS",
    "created_at": "2026-06-01T10:00:00Z",
    "updated_at": "2026-06-09T14:30:45.123Z"
  }
}
```

### Change Summary Format
```json
{
  "changed_fields": ["status", "room_id", "amount_paid"],
  "status_change": {
    "from": "fully_paid",
    "to": "checked_in"
  },
  "room_assignment": {
    "from": null,
    "to": 42
  },
  "amount_paid_change": {
    "from": 0.00,
    "to": 450.00
  }
}
```

---

## API Endpoints (Suggested)

### Query Audit Logs
```
GET /api/v1/hotels/{hotel_id}/audit/events
  ?entity_type=reservation
  &entity_id=12345
  &action_code=update
  &user_id=5
  &date_from=2026-06-01
  &date_to=2026-06-30
  &limit=100
  &offset=0
Response: { items: [...], total: N, has_more: bool }
```

### Get Detailed Changes for Event
```
GET /api/v1/hotels/{hotel_id}/audit/events/{event_id}
Response: {
  event: {...},
  field_changes: [
    {
      field_name: "status",
      old_value: "pending",
      new_value: "deposit_paid",
      data_type: "enum"
    }
  ]
}
```

### Search Audit Trail
```
POST /api/v1/hotels/{hotel_id}/audit/search
{
  "query": "room_id changed",
  "entity_type": "reservation",
  "date_range": {"start": "2026-06-01", "end": "2026-06-30"}
}
Response: [...events matching criteria...]
```

### Audit Webhooks Management
```
POST /api/v1/hotels/{hotel_id}/audit/webhooks
GET /api/v1/hotels/{hotel_id}/audit/webhooks
PATCH /api/v1/hotels/{hotel_id}/audit/webhooks/{webhook_id}
DELETE /api/v1/hotels/{hotel_id}/audit/webhooks/{webhook_id}
```

---

## Triggers & Hooks (Python/SQLAlchemy)

### Auto-capture on Session Flush

```python
def _audit_before_insert(mapper, connection, target):
    """Capture entity creation."""
    # Log CREATE event with after_json snapshot
    
def _audit_before_update(mapper, connection, target):
    """Capture entity changes."""
    # Log UPDATE event with before/after snapshots
    # Create audit_log_entries for each changed field
    
def _audit_before_delete(mapper, connection, target):
    """Capture entity deletion."""
    # Log DELETE event with before_json snapshot
```

### Event Correlation (Request Context)

```python
# Middleware captures request_id in contextvars
from contextvars import ContextVar
audit_request_id: ContextVar[str] = ContextVar('audit_request_id')

# On each database action, retrieve and include in AuditEvent.request_id
```

---

## Query Patterns

### Timeline of Changes to a Reservation
```sql
SELECT 
  event.id, event.action_code, event.user_id, event.created_at,
  change.field_name, change.old_value, change.new_value
FROM hotel_audit_events event
LEFT JOIN audit_log_entries change ON event.id = change.hotel_audit_event_id
WHERE event.entity_type = 'reservation' 
  AND event.entity_id = 12345
ORDER BY event.created_at DESC
```

### All Changes by User in Date Range
```sql
SELECT event.* FROM hotel_audit_events event
WHERE event.hotel_id = 1
  AND event.user_id = 5
  AND event.created_at BETWEEN '2026-06-01' AND '2026-06-30'
ORDER BY event.created_at DESC
LIMIT 100
```

### Deletion Audit Trail
```sql
SELECT event.* FROM hotel_audit_events event
WHERE event.hotel_id = 1
  AND event.action_code = 'delete'
  AND event.created_at >= NOW() - INTERVAL '7 days'
ORDER BY event.created_at DESC
```

### Find Unauthorized Access Attempts
```sql
SELECT event.* FROM hotel_audit_events event
WHERE event.hotel_id = 1
  AND event.ip_address NOT IN (
    SELECT DISTINCT ip_address FROM hotel_audit_events 
    WHERE user_id = event.user_id
    AND created_at < event.created_at - INTERVAL '30 days'
  )
ORDER BY event.created_at DESC
```

---

## Retention & Compliance

### Default Retention Policy
- **Reservations & Financial:** 7 years (2555 days) - Fiscal/Tax compliance
- **User Activity & Admin:** 2 years (730 days) - SOX compliance
- **OTA Syncs & System:** 1 year (365 days) - Operational reference
- **Deletions & Cancellations:** 10 years (3650 days) - Legal hold

### Redaction Rules
```json
{
  "reservation": {
    "guest_id": "REDACTED_REFERENCE",
    "cc_last_4": "****",
    "guest_phone": "REDACTED_PHONE"
  },
  "user": {
    "password_hash": "REDACTED_HASH",
    "email": "REDACTED_EMAIL"
  }
}
```

### Archive Strategy
- Monthly cold-storage archives to S3 (gzip JSON)
- Immutable lock after 90 days
- Encrypt with customer-supplied KMS key
- SHA256 integrity verification

---

## Performance Considerations

### Indexing Strategy
```sql
-- Fast entity timeline queries
CREATE INDEX ix_audit_events_entity ON hotel_audit_events(entity_type, entity_id, created_at DESC);

-- Fast user activity tracking
CREATE INDEX ix_audit_events_user_time ON hotel_audit_events(user_id, created_at DESC);

-- Fast action filtering
CREATE INDEX ix_audit_events_hotel_action ON hotel_audit_events(hotel_id, action_code, created_at DESC);

-- Request correlation
CREATE INDEX ix_audit_events_request_id ON hotel_audit_events(request_id) WHERE request_id IS NOT NULL;
```

### Partitioning (PostgreSQL)
```sql
-- Partition by hotel_id + year_month for scale
CREATE TABLE hotel_audit_events_2026_06 PARTITION OF hotel_audit_events
  FOR VALUES FROM ('2026-06-01') TO ('2026-07-01')
  WHERE hotel_id = ANY(ARRAY[...]);
```

### Write Optimization
- Batch audit entries for multi-field updates
- Async webhook dispatch (don't block transaction)
- Lazy-load field details (only when requested)
- Compress old JSON blobs

---

## Security Considerations

### Access Control
- Audit logs visible only to: Hotel Admin, Finance, Compliance roles
- Deletions/edits of audit logs forbidden (append-only)
- Audit log access itself is audited

### Data Protection
- PII redaction on non-admin views
- IP addresses masked by default (show only if GDPR-relevant)
- Passwords/tokens never stored in plaintext snapshots
- Sensitive fields encrypted at rest

### Anti-Tampering
- Digital signature on archived audit logs
- Blockchain hash chain (optional: link each month to previous)
- Immutable lock-down after retention expires

---

## Implementation Roadmap

**Phase 1 - Foundation (Week 1)**
- [x] `HotelAuditEvent` table (already exists)
- [ ] Migration: Add missing columns (change_summary, source_code, request_id, ip_address)
- [ ] `AuditLogEntry` table for field-level tracking
- [ ] SQLAlchemy event hooks (before_insert/update/delete)

**Phase 2 - Context Capture (Week 2)**
- [ ] Request middleware to capture user, IP, request_id
- [ ] Entity snapshot utilities (to_audit_dict)
- [ ] Diff/comparison logic for before/after

**Phase 3 - Compliance (Week 3)**
- [ ] `AuditRetentionPolicy` table
- [ ] `AuditLogArchive` table
- [ ] Archive job (monthly cold-storage)
- [ ] Redaction rules engine

**Phase 4 - Webhooks & Alerts (Week 4)**
- [ ] `AuditWebhook` & `AuditWebhookEvent` tables
- [ ] Webhook dispatcher (async task)
- [ ] Retry logic & backoff

**Phase 5 - API & Dashboard (Week 5)**
- [ ] Audit query endpoints
- [ ] Audit timeline visualization
- [ ] Export reports (CSV, PDF)
- [ ] Compliance report generation

---

## Example: Capturing a Reservation Update

```python
# User updates reservation status: pending → deposit_paid

# 1. Request context middleware
audit_request_id.set(str(uuid4()))

# 2. SQLAlchemy before_update hook fires
@event.listens_for(Reservation, "before_update")
def audit_reservation_update(mapper, connection, target):
    db_obj = connection.execute(
        select(Reservation).where(Reservation.id == target.id)
    ).scalar()
    
    old_snapshot = db_obj.to_audit_dict()
    new_snapshot = target.to_audit_dict()
    
    # Create event
    event_obj = HotelAuditEvent(
        hotel_id=target.hotel_id,
        user_id=get_current_user_id(),
        action_code=ActionCodeEnum.UPDATE,
        entity_type=EntityTypeEnum.RESERVATION,
        entity_id=target.id,
        before_json=json.dumps(old_snapshot),
        after_json=json.dumps(new_snapshot),
        source_code=SourceCodeEnum.API,
        ip_address=get_request_ip(),
        request_id=audit_request_id.get()
    )
    
    # Diff fields
    for field, new_val in new_snapshot.items():
        old_val = old_snapshot.get(field)
        if old_val != new_val:
            AuditLogEntry(
                hotel_audit_event_id=event_obj.id,
                field_name=field,
                old_value=str(old_val),
                new_value=str(new_val),
                data_type=type(new_val).__name__
            )
    
    connection.execute(insert(HotelAuditEvent), [event_obj])
```

---

## Testing Strategy

```python
def test_audit_event_created_on_reservation_insert():
    res = create_reservation(...)
    db.commit()
    
    audit = db.query(HotelAuditEvent).filter_by(
        entity_id=res.id,
        entity_type=EntityTypeEnum.RESERVATION,
        action_code=ActionCodeEnum.CREATE
    ).first()
    
    assert audit is not None
    assert json.loads(audit.after_json)["id"] == res.id

def test_audit_captures_field_changes():
    res = create_reservation(...)
    res.status = ReservationStatusEnum.DEPOSIT_PAID
    db.commit()
    
    changes = db.query(AuditLogEntry).filter_by(
        field_name="status"
    ).all()
    
    assert len(changes) == 1
    assert changes[0].old_value == "pending"
    assert changes[0].new_value == "deposit_paid"

def test_retention_policy_enforced():
    # Create old events
    event = create_old_audit_event(days_ago=800)
    db.commit()
    
    # Run cleanup job
    cleanup_expired_audit_logs()
    
    # Check archived
    assert db.query(HotelAuditEvent).filter_by(id=event.id).first() is None
    assert db.query(AuditLogArchive).count() > 0
```

---

## References & Standards

- **SOX Compliance:** 404(b) - Audit trail for financial controls
- **GDPR:** Article 32 - Audit logs for data processing
- **PCI-DSS:** Requirement 10 - Logging & monitoring
- **ISO 27001:** A.12.4.1 - Event logging
- **HIPAA:** 45 CFR 164.312(b) - Audit controls

---

**End of Schema Design Document**
