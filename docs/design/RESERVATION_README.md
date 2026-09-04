# Reservation Module - Implementation Guide

## Overview

This directory contains a complete design specification and code skeleton for the Hotel PMS Reservation Module. The module handles the full lifecycle of guest reservations from booking through checkout, with a strict state machine enforcing valid state transitions.

## Documents Included

### 1. **RESERVATION_MODULE_DESIGN.md** (Main Design Doc)
Comprehensive specification including:
- State machine diagram and transitions
- Complete database model with all fields and relationships
- Pydantic schemas for API contracts
- Service layer with all business logic functions
- Complete CRUD endpoint specifications
- Error handling and validation rules
- Relationship diagrams
- Implementation checklist

**Read this first** to understand the overall architecture.

### 2. **RESERVATION_CODE_SKELETON.py** (Ready-to-Implement Code)
Copy-paste ready code with [IMPLEMENT] markers showing what needs to be filled in:
- Pydantic schemas (ReservationCreate, ReservationRead, ReservationUpdate)
- Service layer functions with docstrings
- API endpoint definitions with FastAPI
- Exception classes
- All with detailed docstrings explaining the logic

**Use this as a template** when implementing the actual code.

### 3. **RESERVATION_QUICK_REFERENCE.md** (Quick Lookup)
Quick reference guide including:
- ASCII state machine diagram
- Relationship diagram
- SQL table structure
- API request/response examples
- Common query patterns
- Business rules summary
- Performance optimization hints
- Testing checklist

**Refer to this frequently** during development.

---

## Key Design Decisions

### 1. State Machine
The reservation follows a strict linear state machine:
```
PENDING → DEPOSIT_PAID → FULLY_PAID → CHECKED_IN → CHECKED_OUT
       ↘ FULLY_PAID (skip deposit) ↙
       ↓ CANCELLED (from PENDING, DEPOSIT_PAID, FULLY_PAID)
       ↓ NO_SHOW (from FULLY_PAID if missed check-in)
```

**Why:** Prevents invalid state transitions. Business logic validates each transition with preconditions (e.g., must be FULLY_PAID before CHECKED_IN).

### 2. Hotel Scoping
Every query filters by `hotel_id` to ensure data isolation in multi-hotel environments.

**Why:** Critical for SaaS security and data privacy.

### 3. Lazy Room Assignment
`room_id` is nullable until assigned, allowing flexibility:
- Create reservation for room category
- Assign specific room later
- Lock assignment once payment received and allocation_locked = true

**Why:** Supports dynamic room assignment, overbooking recovery, and room upgrades.

### 4. Financial Snapshot Fields
Stores original pricing (`pricing_snapshot`, `fx_rate_snapshot`) to track price changes over time.

**Why:** Audit trail for dispute resolution and financial reconciliation.

### 5. Additional Guests Association
Many-to-many table for secondary occupants (spouse, friends, etc.).

**Why:** Tracking all guests on the reservation for occupancy verification and check-in processing.

### 6. OTA Integration Fields
Dedicated fields for external booking integration:
- `source`: Which OTA (Booking.com, Expedia, etc.) or direct
- `external_id`: OTA booking ID
- `source_provider_code`: Custom tracking
- `payment_collection_model`: Who collects payment

**Why:** Separate OTA sync logic from core reservation logic.

### 7. Arrival and Internal Request Metadata

Reservations also expose two independent operational fields:

- `arrival_time_hint`: optional estimated arrival time in local hotel time,
  normalized as `HH:MM`.
- `reservation_comment`: optional internal hotel-team request, trimmed and
  limited to 1000 characters. Empty values are stored as `NULL` and the field
  remains separate from the legacy `notes` field.

Both fields can be edited with `reservation:update` while a reservation is not
soft-deleted, including terminal states. Every change is recorded in the
existing reservation audit activity with before/after values. Public creation
accepts the fields, but public responses expose only `arrival_time_hint`; the
internal comment is never returned publicly. OTA updates may refresh the
arrival hint but must preserve the internal comment.

---

## Data Model Highlights

### Core Fields
```
Reservation {
  id: Primary Key
  confirmation_code: Unique, human-readable (HOTE20240615ABC)
  hotel_id: Multi-hotel scoping
  guest_id: Primary guest (required)
  room_id: Assigned room (nullable until assigned)
  category_id: Room category (required for pricing)
  
  check_in_date, check_out_date: Stay dates
  actual_check_in, actual_check_out: Filled on checkin/checkout
  
  status: State machine (PENDING, DEPOSIT_PAID, FULLY_PAID, CHECKED_IN, CHECKED_OUT, CANCELLED, NO_SHOW)
  outcome: Summary (PENDING, CHECKED_IN, COMPLETED, CANCELLED, NO_SHOW)
  
  total_amount: Final price guest pays (ARS)
  amount_paid: Cumulative payments received
  balance_due: Computed (total - paid)
  
  allocation_status: "unassigned", "assigned", "locked"
  requires_manual_review: Flag for staff action needed
  
  created_at, updated_at: Timestamps (UTC)
}
```

### Relationships
- **Guest** (1:1 required) - Primary guest
- **Additional Guests** (M:M optional) - Secondary occupants
- **Room** (1:1 optional) - Assigned room
- **RoomCategory** (1:1 required) - Room type (Double, Single, Suite)
- **RatePlan** (1:1 optional) - Pricing model
- **TaxPolicy** (1:1 optional) - Tax calculation rules
- **Company** (1:1 optional) - B2B corporate client
- **SellableProduct** (1:1 optional) - Package/add-on product
- **Transactions** (1:N) - Payment records
- **OperationalEvents** (1:N) - Audit log (room moves, extends, etc.)

---

## Implementation Strategy

### Phase 1: Foundation (Models & Schemas)
1. Verify `app/models/reservation.py` exists and is complete
2. Create `app/schemas/reservation.py` with Pydantic models
3. Write unit tests for model validations

**Estimated Time:** 2-4 hours
**Risk:** Low (no business logic)

### Phase 2: Business Logic (Service Layer)
1. Create `app/services/reservation_service.py`
2. Implement all service functions (15 functions)
3. Test with unit tests
4. Add event emission hooks

**Estimated Time:** 8-12 hours
**Risk:** Medium (complex state machine, availability logic)

### Phase 3: API Endpoints
1. Create/update `app/api/reservations.py`
2. Implement all endpoints (15+ endpoints)
3. Register router in `app/main.py`
4. Write integration tests

**Estimated Time:** 6-10 hours
**Risk:** Medium (role-based access, error handling)

### Phase 4: Advanced Features
1. Room assignment logic
2. Room move operations
3. Stay extension with repricing
4. Timeline/audit endpoints
5. Batch availability checks

**Estimated Time:** 4-8 hours
**Risk:** Medium

### Phase 5: Testing & Optimization
1. Full test coverage
2. Query optimization with indexes
3. Caching strategy
4. Load testing
5. Documentation

**Estimated Time:** 6-10 hours
**Risk:** Low

**Total Estimated Effort:** 26-44 hours (3-5 days for experienced developer)

---

## Critical Business Rules

### State Transitions
1. **PENDING** → Can transition to DEPOSIT_PAID, FULLY_PAID, or CANCELLED
2. **DEPOSIT_PAID** → Can transition to FULLY_PAID or CANCELLED
3. **FULLY_PAID** → Can transition to CHECKED_IN, CANCELLED, or NO_SHOW
4. **CHECKED_IN** → Can ONLY transition to CHECKED_OUT
5. **CHECKED_OUT**, **CANCELLED**, **NO_SHOW** → Terminal states (no transitions)

### Check-In Preconditions
- Status must be FULLY_PAID
- Room must be assigned (room_id ≠ null)
- Current date ≥ check_in_date
- Guest capacity must be satisfied (room capacity ≥ adults + children)

### Check-Out Operations
1. Record actual_check_out timestamp
2. Calculate final charges (late checkout fees, damages, etc.)
3. Transition to CHECKED_OUT (terminal)
4. Emit audit event

### Cancellation
- Cannot cancel after CHECKED_IN
- Process refunds per cancellation policy
- Release room allocation
- Record cancellation reason and user

### No-Show
- Applied when guest doesn't check in by deadline
- Charge per no-show policy (full/partial/waived)
- Terminal state (cannot recover to CHECKED_IN)

### Room Availability
- Two date ranges overlap if: `new_checkin < existing_checkout AND new_checkout > existing_checkin`
- Exclude cancelled and no-show reservations (they don't occupy the room)
- Filter by room capacity and category compatibility

---

## Testing Strategy

### Unit Tests
- Model validations (dates, amounts)
- Computed properties
- State machine rules
- Service function logic
- Error cases

### Integration Tests
- Full workflows (create → pay → check in → check out)
- Cancellation with refunds
- Room assignment and moves
- Availability checking
- Multi-hotel isolation

### E2E Tests
- Frontend to backend complete flows
- Concurrent bookings (race conditions)
- OTA sync scenarios
- Error handling and recovery

### Load Tests
- Availability checks (frequent query)
- List reservations with various filters
- Concurrent check-ins
- Batch operations

---

## Common Pitfalls & Solutions

### Pitfall 1: Date Range Overlap
**Problem:** Incorrect overlap detection allows double-booking
**Solution:** Use correct formula: `a.start < b.end AND a.end > b.start`
**Test:** Create 2 reservations with overlapping dates

### Pitfall 2: Double Payments
**Problem:** Two payments recorded for same amount
**Solution:** Use transaction records with idempotency keys
**Test:** Retry payment endpoint with same data

### Pitfall 3: Soft Delete Confusion
**Problem:** Cancelled reservations still appear in queries
**Solution:** Always filter `WHERE status != 'cancelled'` unless specifically requested
**Test:** Create and cancel reservation, verify not in list

### Pitfall 4: State Machine Violations
**Problem:** Allow transition from CHECKED_OUT back to CANCELLED
**Solution:** Check VALID_TRANSITIONS dict before any transition
**Test:** Try all invalid transitions, verify they fail

### Pitfall 5: Hotel Scope Leaks
**Problem:** User can see reservations from other hotels
**Solution:** ALWAYS filter by `hotel_id = context.hotel_id`
**Test:** User from Hotel A tries to access Hotel B's reservation

### Pitfall 6: Race Condition in Room Assignment
**Problem:** Two reservations assign same room concurrently
**Solution:** Use database transactions with SELECT FOR UPDATE
**Test:** Load test concurrent room assignments

---

## Files to Create/Modify

### New Files to Create
```
app/schemas/reservation.py               # Pydantic schemas
app/services/reservation_service.py      # Business logic
(Update existing:)
app/api/reservations.py                 # HTTP endpoints
app/models/reservation.py                # ORM model (should exist)
app/main.py                              # Register router
```

### Database Migrations
```
alembic/versions/XXXXX_reservation_schema.py
```

### Tests
```
tests/unit/test_reservation_models.py
tests/unit/test_reservation_service.py
tests/integration/test_reservations_api.py
tests/e2e/test_reservation_workflows.py
```

### Documentation
```
docs/RESERVATION_API.md                  # API documentation
docs/RESERVATION_BUSINESS_RULES.md       # Business rules
docs/RESERVATION_SEQUENCE_DIAGRAMS.md    # Sequence diagrams
```

---

## Quick Start

1. **Read Documents** (30 min)
   - Start with RESERVATION_QUICK_REFERENCE.md
   - Skim RESERVATION_MODULE_DESIGN.md for deep understanding

2. **Set Up Code** (1 hour)
   - Copy RESERVATION_CODE_SKELETON.py into appropriate files
   - Create directory structure

3. **Implement Step by Step** (Follow Phase 1-5 above)
   - Test each phase before moving to next
   - Run tests frequently

4. **Integration & Testing** (2-3 days)
   - Full test coverage
   - Performance testing
   - Load testing

5. **Documentation** (1 day)
   - API spec generation (FastAPI auto-generates from docstrings)
   - Business rules documentation
   - Runbook for operations

---

## API Contract Summary

### CRUD Operations
```
POST   /api/reservations/              Create
GET    /api/reservations/              List (with filters)
GET    /api/reservations/{id}          Get one
PATCH  /api/reservations/{id}          Update (safe fields only)
DELETE /api/reservations/{id}          Delete (only if PENDING & unpaid)
```

### State Transitions
```
POST   /api/reservations/{id}/mark-paid        PENDING → DEPOSIT_PAID/FULLY_PAID
POST   /api/reservations/{id}/check-in         FULLY_PAID → CHECKED_IN
POST   /api/reservations/{id}/check-out        CHECKED_IN → CHECKED_OUT
POST   /api/reservations/{id}/cancel           Any → CANCELLED
POST   /api/reservations/{id}/mark-no-show     FULLY_PAID → NO_SHOW
```

### Advanced Operations
```
POST   /api/reservations/{id}/assign-room      Assign room
POST   /api/reservations/{id}/move-room        Move guest to different room
POST   /api/reservations/{id}/extend-stay      Extend check-out date
POST   /api/reservations/verify-availability   Batch room availability check
GET    /api/reservations/{id}/timeline         Get status change history
```

---

## Success Criteria

A complete implementation should:

1. **Model Correctness**
   - [ ] All fields present with correct types
   - [ ] All constraints enforced
   - [ ] Relationships defined correctly
   - [ ] Computed properties work

2. **Service Layer Quality**
   - [ ] All functions implemented
   - [ ] Comprehensive error handling
   - [ ] Event emission working
   - [ ] Unit tests passing (>90% coverage)

3. **API Completeness**
   - [ ] All endpoints working
   - [ ] Proper HTTP status codes
   - [ ] Role-based access control enforced
   - [ ] Hotel isolation verified

4. **Business Logic**
   - [ ] State machine enforced
   - [ ] Availability checking accurate
   - [ ] Cancellation with refunds working
   - [ ] Multi-hotel support verified

5. **Testing**
   - [ ] Unit tests passing
   - [ ] Integration tests passing
   - [ ] E2E workflows working
   - [ ] No race conditions

6. **Performance**
   - [ ] Availability queries < 200ms
   - [ ] List queries with pagination working
   - [ ] Database indexes created
   - [ ] Load test passing (100+ concurrent requests)

---

## Support & Debugging

### Common Errors

**"check_out_date must be after check_in_date"**
- Ensure dates are in correct order in request

**"Room not available for requested dates"**
- Check date overlap with existing reservations
- Verify room status is operational

**"Cannot transition from CHECKED_OUT to CANCELLED"**
- State machine violation; cannot cancel terminal states
- This is by design for audit trail

**"Subscription inactive"**
- Hotel subscription not active; check billing status

**"Unauthorized"**
- User lacks required role
- Check context.user_id and required_roles()

### Debugging Tips

1. **Enable logging**
   ```python
   import logging
   logging.basicConfig(level=logging.DEBUG)
   ```

2. **Check database state**
   ```sql
   SELECT * FROM reservations WHERE id = 1001;
   SELECT * FROM transactions WHERE reservation_id = 1001;
   ```

3. **Verify relationships loaded**
   ```python
   assert reservation.guest is not None
   assert reservation.room is not None
   ```

4. **Test state transitions individually**
   ```python
   res = get_reservation(db, 1001, hotel_id)
   print(f"Current status: {res.status}")
   transition_reservation_status(db, 1001, hotel_id, ReservationStatusEnum.CHECKED_IN)
   ```

---

## Next Steps

1. Create the Python files from RESERVATION_CODE_SKELETON.py
2. Implement all [IMPLEMENT] sections
3. Write comprehensive tests
4. Integrate with frontend
5. Deploy and monitor

Good luck with implementation!
