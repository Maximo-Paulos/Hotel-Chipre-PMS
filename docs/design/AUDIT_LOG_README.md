# Audit Logging Module - Implementation Guide

**Status:** Schema & Service Layer Complete  
**Version:** 1.0.0  
**Date:** 2026-06-09

---

## Quick Start

### 1. Models
All audit models are in `app/models/audit.py`:
- `HotelAuditEvent` - Main event table (replaces analytics version)
- `AuditLogEntry` - Field-level change tracking
- `AuditRetentionPolicy` - Compliance configuration
- `AuditLogArchive` - Cold storage metadata
- `AuditWebhook` - Event notification configuration
- `AuditWebhookEvent` - Webhook delivery tracking

### 2. Service
The `AuditService` in `app/services/audit_service.py` provides:
```python
from app.services.audit_service import AuditService, AuditContext

# Option A: Direct service
service = AuditService(db)
event = service.record_change(
    hotel_id=1,
    user_id=5,
    entity_type=EntityTypeEnum.RESERVATION,
    entity_id=12345,
    action_code=ActionCodeEnum.UPDATE,
    before_snapshot=old_data,
    after_snapshot=new_data,
    source_code=SourceCodeEnum.API,
)

# Option B: Context manager
with AuditContext(db, user_id=5, hotel_id=1) as audit:
    audit.record_change(
        entity_type=EntityTypeEnum.RESERVATION,
        entity_id=12345,
        action_code=ActionCodeEnum.UPDATE,
        before_snapshot=old_data,
        after_snapshot=new_data,
    )
```

### 3. Migration
Run the migration to create all tables:
```bash
alembic upgrade 20260609_audit_schema_v1
```

---

## Architecture

### Data Flow

```
Entity Change
    ↓
SQLAlchemy Event Hook (before_insert/update/delete)
    ↓
Capture Before/After Snapshots
    ↓
AuditService.record_change()
    ↓
HotelAuditEvent + AuditLogEntry created
    ↓
Request context (user_id, ip_address, request_id) attached
    ↓
Webhook triggers (async)
    ↓
Database commit
    ↓
Events visible to queries
```

### Table Relationships

```
hotel_audit_events_v2 (main events)
    ├── 1:N → audit_log_entries (field changes)
    ├── N:1 ← audit_webhooks (subscriptions)
    │         └── 1:N → audit_webhook_events (delivery tracking)
    ├── N:1 ← audit_retention_policies (compliance rules)
    └── N:1 ← audit_log_archives (cold storage)
```

---

## Core Concepts

### Audit Event
Records a single change to an entity:
- **Who:** user_id
- **What:** entity_type + entity_id + action_code
- **When:** created_at (UTC)
- **Where:** source_code (API, OTA, Manual, System)
- **Why:** reason_code + change_summary
- **Snapshots:** before_json + after_json (full state)

### Field Change
Records an individual field within an event:
- Which field changed
- Data type (string, integer, enum, etc.)
- Old → New values
- Whether field was/is NULL
- Whether change was system-generated

### Request Context
All events in a single request share:
- `request_id` (UUID) - Correlate related changes
- `user_id` - Who made the change
- `ip_address` - Where from
- `source_code` - How it originated

### Retention Policy
Compliance-driven lifecycle:
- Retention period (e.g., 7 years for reservations)
- Archive threshold (e.g., 90 days → cold storage)
- Redaction rules (PII handling)
- Entity-type specific or hotel-wide default

---

## Query Patterns

### Get Timeline for Entity
```python
service = AuditService(db)
events, total = service.get_entity_timeline(
    hotel_id=1,
    entity_type=EntityTypeEnum.RESERVATION,
    entity_id=12345,
    limit=100,
    offset=0,
)

for event in events:
    print(f"{event.created_at} {event.action_code}")
    for change in event.field_changes:
        print(f"  {change.field_name}: {change.old_value} → {change.new_value}")
```

### Get User Activity
```python
events, total = service.get_user_activity(
    hotel_id=1,
    user_id=5,
    date_from=datetime(2026, 6, 1),
    date_to=datetime(2026, 6, 30),
    action_codes=[ActionCodeEnum.DELETE, ActionCodeEnum.CANCEL],
    limit=100,
)
```

### Find All Deletions
```python
deletions = service.get_action_audit(
    hotel_id=1,
    action_code=ActionCodeEnum.DELETE,
    entity_type=EntityTypeEnum.RESERVATION,
    days_back=7,
)
```

### Raw SQL Example
```sql
-- All changes to a reservation with field-level detail
SELECT 
  e.created_at,
  e.action_code,
  e.user_id,
  f.field_name,
  f.old_value,
  f.new_value
FROM hotel_audit_events_v2 e
LEFT JOIN audit_log_entries f ON e.id = f.hotel_audit_event_id
WHERE e.hotel_id = 1
  AND e.entity_type = 'reservation'
  AND e.entity_id = 12345
ORDER BY e.created_at DESC;
```

---

## Integration Points

### 1. SQLAlchemy Event Hooks (Optional Auto-Capture)

To automatically capture all changes (without manual `record_change()` calls):

```python
# In app/database.py or new app/services/audit_hooks.py

from sqlalchemy import event
from app.models.audit import AuditService
from app.models.reservation import Reservation
from contextvars import ContextVar

# Store current user/request info in context
current_audit_context: ContextVar[dict] = ContextVar('audit', default={})

@event.listens_for(Reservation, 'before_insert')
def audit_before_insert(mapper, connection, target):
    ctx = current_audit_context.get()
    service = AuditService(connection)
    
    service.record_change(
        hotel_id=target.hotel_id,
        user_id=ctx.get('user_id', 0),
        entity_type=EntityTypeEnum.RESERVATION,
        entity_id=None,  # New entity
        action_code=ActionCodeEnum.CREATE,
        before_snapshot=None,
        after_snapshot=target.to_audit_dict(),
        source_code=ctx.get('source_code', SourceCodeEnum.SYSTEM),
        ip_address=ctx.get('ip_address'),
        request_id=ctx.get('request_id'),
    )

@event.listens_for(Reservation, 'before_update')
def audit_before_update(mapper, connection, target):
    # ... similar to insert but capture before snapshot
    pass

@event.listens_for(Reservation, 'before_delete')
def audit_before_delete(mapper, connection, target):
    # ... capture deletion
    pass
```

### 2. API Middleware (Request Context)

Capture user, IP, request_id for all requests:

```python
# In app/main.py or new middleware file

import uuid
from contextvars import ContextVar
from starlette.middleware.base import BaseHTTPMiddleware

audit_context: ContextVar[dict] = ContextVar('audit')

class AuditContextMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        # Extract or generate request ID
        request_id = request.headers.get('X-Request-ID', str(uuid.uuid4()))
        
        # Get user from JWT/session
        user_id = getattr(request.state, 'user_id', 0)
        
        # Get client IP
        ip_address = request.client.host
        
        # Store in context
        audit_context.set({
            'request_id': request_id,
            'user_id': user_id,
            'ip_address': ip_address,
            'source_code': SourceCodeEnum.API,
        })
        
        response = await call_next(request)
        return response

app.add_middleware(AuditContextMiddleware)
```

### 3. Webhook Integration

Set up webhook to notify external systems:

```python
# Create webhook for compliance system
service.record_webhook_config(
    hotel_id=1,
    name="Compliance Lambda",
    webhook_url="https://compliance.example.com/audit",
    action_codes=["DELETE", "CANCEL"],
    entity_types=["RESERVATION", "PAYMENT"],
    secret_token="xxx",
)

# On audit event creation, trigger webhooks
# (implement as async Celery task or background job)
for webhook in webhooks:
    if webhook_matches_event(webhook, event):
        trigger_webhook_delivery.delay(webhook.id, event.id)
```

### 4. Retention Cleanup Job

Run periodically to archive old logs:

```python
# Celery task or APScheduler job

@app.task
def archive_expired_audit_logs():
    from app.services.audit_archive import archive_hotel_logs
    
    db = get_db()
    for hotel in get_all_hotels():
        policy = service.get_retention_policy(hotel.id)
        if policy:
            archive_days = policy.archive_after_days
            expired = service.find_expired_logs(hotel.id, days_old=archive_days)
            
            if expired:
                archive_hotel_logs(hotel.id, expired, db)
```

---

## API Endpoints (Suggested Implementation)

### Get Audit Timeline
```
GET /api/v1/hotels/{hotel_id}/audit/events/{entity_type}/{entity_id}
```
Parameters:
- `limit` (int, default 100)
- `offset` (int, default 0)

Response:
```json
{
  "items": [
    {
      "id": 1,
      "action_code": "update",
      "user_id": 5,
      "created_at": "2026-06-09T14:30:45Z",
      "before_json": {...},
      "after_json": {...},
      "field_changes": [
        {
          "field_name": "status",
          "old_value": "pending",
          "new_value": "deposit_paid",
          "data_type": "enum"
        }
      ]
    }
  ],
  "total": 42,
  "has_more": true
}
```

### Get User Activity
```
GET /api/v1/hotels/{hotel_id}/audit/user/{user_id}
```
Parameters:
- `date_from`, `date_to` (ISO 8601)
- `action_codes` (CSV)
- `limit`, `offset`

### Manage Webhooks
```
POST /api/v1/hotels/{hotel_id}/audit/webhooks
GET /api/v1/hotels/{hotel_id}/audit/webhooks
PATCH /api/v1/hotels/{hotel_id}/audit/webhooks/{webhook_id}
DELETE /api/v1/hotels/{hotel_id}/audit/webhooks/{webhook_id}
```

### Compliance Report
```
GET /api/v1/hotels/{hotel_id}/audit/compliance-report
```
Parameters:
- `date_from`, `date_to`
- `format` (json, csv, pdf)

---

## Entity Snapshots (to_audit_dict())

Each entity needs a method to serialize for audit:

```python
# In app/models/reservation.py

class Reservation(Base):
    # ... columns ...
    
    def to_audit_dict(self) -> dict:
        """Export data for audit log snapshot."""
        return {
            'id': self.id,
            'confirmation_code': self.confirmation_code,
            'guest_id': self.guest_id,
            'room_id': self.room_id,
            'status': self.status.value if self.status else None,
            'check_in_date': self.check_in_date.isoformat() if self.check_in_date else None,
            'check_out_date': self.check_out_date.isoformat() if self.check_out_date else None,
            'total_amount': float(self.total_amount),
            'amount_paid': float(self.amount_paid),
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'updated_at': self.updated_at.isoformat() if self.updated_at else None,
        }
```

---

## Security Considerations

### PII Redaction
Some fields shouldn't appear in audit logs for non-admin users:
- Passwords (never, even hashed)
- Credit card data
- Phone numbers
- Email addresses (in some contexts)
- Health/legal information

Configure via `AuditRetentionPolicy.redaction_rules`:
```json
{
  "guest": {
    "phone": "REDACTED_PHONE",
    "email": "REDACTED_EMAIL",
    "passport_number": "REDACTED_ID"
  },
  "user": {
    "password_hash": "REDACTED_HASH",
    "email": "REDACTED_EMAIL"
  }
}
```

### Access Control
- Audit logs are **read-only** (append-only design)
- Only Hotel Admins can view (filter by hotel_id)
- Staff can only see changes they made
- System logs access to audit logs themselves

### Data Protection
- Encrypt sensitive fields at rest
- IP addresses masked for non-security staff
- Archive digital signatures for tamper-detection
- Immutable lock after retention period expires

---

## Performance Tips

### Indexing
The migration creates indexes for common queries:
- `(hotel_id, created_at)` - Timeline queries
- `(hotel_id, action_code)` - Filter by action
- `(entity_type, entity_id)` - Find changes to entity
- `(user_id, created_at)` - User activity

### Archival Strategy
1. Keep recent 90 days in main database
2. Archive older logs to S3 (gzip JSON monthly)
3. Compress with SHA256 integrity check
4. Lock after 90 days (prevent modification)
5. Delete after retention period expires

### Batch Operations
If inserting many audit entries:
```python
events = [
    HotelAuditEvent(...),
    HotelAuditEvent(...),
    # ...
]
db.bulk_insert_mappings(HotelAuditEvent, events)
db.commit()
```

---

## Testing

### Unit Test Example
```python
def test_record_change_creates_event_and_entries(db):
    service = AuditService(db)
    
    event = service.record_change(
        hotel_id=1,
        user_id=5,
        entity_type=EntityTypeEnum.RESERVATION,
        entity_id=12345,
        action_code=ActionCodeEnum.UPDATE,
        before_snapshot={'status': 'pending'},
        after_snapshot={'status': 'deposit_paid'},
    )
    
    assert event.id is not None
    assert event.action_code == ActionCodeEnum.UPDATE
    assert len(event.field_changes) == 1
    assert event.field_changes[0].field_name == 'status'
    assert event.field_changes[0].old_value == 'pending'
    assert event.field_changes[0].new_value == 'deposit_paid'

def test_retention_policy_controls_cleanup(db):
    service = AuditService(db)
    
    # Create policy: 365 days retention, archive after 90
    policy = service.set_retention_policy(
        hotel_id=1,
        entity_type='reservation',
        retention_days=365,
        archive_after_days=90,
        updated_by_user_id=1,
    )
    
    retrieved = service.get_retention_policy(1, 'reservation')
    assert retrieved.retention_days == 365
    assert retrieved.archive_after_days == 90

def test_webhook_delivery_tracked(db):
    service = AuditService(db)
    
    webhook_event = service.record_webhook_delivery(
        audit_webhook_id=1,
        hotel_audit_event_id=10,
        status=WebhookStatusEnum.DELIVERED,
        http_status=200,
    )
    
    assert webhook_event.status == WebhookStatusEnum.DELIVERED
    assert webhook_event.http_status == 200
```

---

## Compliance & Standards

### Regulatory Requirements Met
- **SOX 404(b):** Audit trail for financial controls
- **GDPR Article 32:** Data processing audit logs
- **PCI-DSS 10:** Logging & monitoring
- **ISO 27001:** Event logging & monitoring
- **HIPAA 45 CFR 164.312(b):** Audit controls

### Default Retention Periods
- Reservations & Financial: **7 years** (tax compliance)
- User Activity & Admin: **2 years** (SOX)
- OTA & System: **1 year** (operational)
- Deletions & Cancellations: **10 years** (legal hold)

---

## Troubleshooting

### No audit events appearing
1. Check migration ran: `select * from hotel_audit_events_v2;`
2. Verify service called: add logging in `record_change()`
3. Check user_id is set correctly
4. Confirm hotel_id matches current context

### Webhook not firing
1. Verify webhook is `is_active=true`
2. Check `action_codes` and `entity_types` match
3. Review `audit_webhook_events` for delivery status
4. Check webhook URL is reachable
5. Verify HMAC signature validation in webhook handler

### Performance degradation
1. Check index usage: `EXPLAIN ANALYZE` on queries
2. Archive old logs (run cleanup job)
3. Consider partitioning by hotel_id
4. Monitor table size: `SELECT pg_size_pretty(pg_total_relation_size('hotel_audit_events_v2'));`

---

## Future Enhancements

### Phase 2 (TBD)
- [ ] Full-text search on change summaries
- [ ] Diff visualization UI
- [ ] Role-based redaction rules
- [ ] Blockchain-style hash chain for immutability
- [ ] Real-time dashboard for compliance

### Phase 3 (TBD)
- [ ] Machine learning anomaly detection
- [ ] Automated compliance report generation
- [ ] Integration with SIEM (Datadog, Splunk)
- [ ] Ledger-style append-only storage (AWS QLDB)

---

## Files & Locations

| File | Purpose |
|------|---------|
| `app/models/audit.py` | ORM models |
| `app/services/audit_service.py` | Service layer & queries |
| `alembic/versions/20260609_audit_schema_v1.py` | Database migration |
| `AUDIT_LOG_SCHEMA.md` | Detailed schema design |
| `AUDIT_LOG_README.md` | This file |

---

## Questions & Support

See `AUDIT_LOG_SCHEMA.md` for:
- Detailed entity relationships
- Complete SQL query examples
- Data type mappings
- Redaction rule formats
- Webhook payload examples

---

**End of Implementation Guide**
