# Reservation Module - Quick Reference Guide

## State Machine Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│                      RESERVATION STATE MACHINE                  │
└─────────────────────────────────────────────────────────────────┘

                           ┌──────────┐
                           │ PENDING  │  (Initial state)
                           └──────┬───┘
                                  │
                    ┌─────────────┼─────────────┐
                    │             │             │
                    ▼             ▼             ▼
            ┌─────────────┐  ┌──────────┐  ┌──────────┐
            │DEPOSIT_PAID │  │FULLY_PAID│  │CANCELLED │
            └──────┬──────┘  └────┬─────┘  └──────────┘
                   │               │       (Terminal)
                   └───────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │ CHECKED_IN   │
                    └──────┬───────┘
                           │
                           ▼
                    ┌──────────────┐
                    │CHECKED_OUT   │
                    └──────────────┘
                    (Terminal)

ALTERNATE PATHS:
- FULLY_PAID → NO_SHOW (after check-in deadline passes, if not checked in)
- PENDING → CANCELLED (before deposit)
- DEPOSIT_PAID → CANCELLED (before full payment)
- FULLY_PAID → CANCELLED (before check-in)

INVARIANTS:
- CHECKED_IN/CHECKED_OUT are terminal states (cannot transition out)
- CANCELLED is terminal
- NO_SHOW is terminal
- Once CHECKED_IN, cannot cancel or mark no-show
```

## Relationship Diagram

```
┌────────────────────────────────────────────────────────────────┐
│                      RESERVATION (Core)                        │
│  id, confirmation_code, status, check_in_date, check_out_date │
│  total_amount, amount_paid, balance_due                        │
└────────────────────────────────────────────────────────────────┘
        │                    │                    │
        │ (1:1)              │ (1:1)              │ (1:1)
        ▼                    ▼                    ▼
    ┌──────────┐         ┌──────────┐         ┌─────────────┐
    │  Guest   │         │  Room    │         │ RoomCategory│
    │(primary) │         │(assigned)│         │  (required) │
    └──────────┘         └──────────┘         └─────────────┘
        │
        │ (M2M)
        ▼
    ┌──────────────────┐
    │Additional Guests │
    │   (secondary)    │
    └──────────────────┘

OPTIONAL LINKS:
┌────────────────────────────────────────────────────────────────┐
│                      RESERVATION                               │
└────────────────────────────────────────────────────────────────┘
        │              │              │              │
   (FK) │              │              │              │ (FK)
        ▼              ▼              ▼              ▼
    ┌────────┐  ┌──────────┐  ┌────────────┐  ┌──────────┐
    │Company │  │RatePlan  │  │TaxPolicy   │  │Sellable  │
    │(B2B)   │  │(pricing) │  │(tax calc)  │  │Product   │
    └────────┘  └──────────┘  └────────────┘  └──────────┘

CHILD RELATIONSHIPS:
┌────────────────────────────────────────────────────────────────┐
│                      RESERVATION                               │
└────────────────────────────────────────────────────────────────┘
        │                          │
   (1:N)│                          │ (1:N, cascade delete)
        ▼                          ▼
    ┌──────────────┐        ┌──────────────────┐
    │ Transaction  │        │OperationalEvent  │
    │ (payments)   │        │(moves, extends)  │
    └──────────────┘        └──────────────────┘
```

## Data Model Essentials

### Reservation Table Structure

```sql
CREATE TABLE reservations (
    id SERIAL PRIMARY KEY,
    confirmation_code VARCHAR(30) UNIQUE NOT NULL,
    hotel_id INT NOT NULL REFERENCES hotel_configuration(id),
    
    -- Guests & Room
    guest_id INT NOT NULL REFERENCES guests(id),
    room_id INT REFERENCES rooms(id),
    category_id INT NOT NULL REFERENCES room_categories(id),
    
    -- Dates
    check_in_date DATE NOT NULL,
    check_out_date DATE NOT NULL,
    actual_check_in TIMESTAMP,
    actual_check_out TIMESTAMP,
    
    -- Financial
    total_amount DECIMAL(10, 2) NOT NULL,
    subtotal_amount DECIMAL(10, 2) NOT NULL,
    tax_amount DECIMAL(10, 2) DEFAULT 0,
    fee_amount DECIMAL(10, 2) DEFAULT 0,
    commission_amount DECIMAL(10, 2) DEFAULT 0,
    net_amount DECIMAL(10, 2) DEFAULT 0,
    deposit_amount DECIMAL(10, 2) DEFAULT 0,
    amount_paid DECIMAL(10, 2) DEFAULT 0,
    
    -- Status
    status ENUM(...) DEFAULT 'pending',
    outcome ENUM(...) DEFAULT 'pending',
    guest_segment ENUM(...) DEFAULT 'leisure',
    channel_code ENUM(...),
    
    -- Cancellation
    cancelled_at TIMESTAMP,
    cancelled_by_user_id INT REFERENCES users(id),
    cancellation_reason_code VARCHAR(50),
    
    -- Metadata
    num_adults INT DEFAULT 1,
    num_children INT DEFAULT 0,
    notes TEXT,
    
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW(),
    
    CONSTRAINT ck_dates CHECK (check_out_date > check_in_date),
    CONSTRAINT ck_amount CHECK (amount_paid <= total_amount),
    
    INDEX ix_hotel_id (hotel_id),
    INDEX ix_guest_id (guest_id),
    INDEX ix_room_id (room_id),
    INDEX ix_status (status),
    INDEX ix_dates (check_in_date, check_out_date)
);
```

## API Request/Response Examples

### 1. Create Reservation

**Request:**
```bash
POST /api/reservations/
Authorization: Bearer <token>
Content-Type: application/json

{
  "guest_id": 42,
  "category_id": 3,
  "room_id": null,  # Will be assigned later
  "check_in_date": "2024-06-15",
  "check_out_date": "2024-06-18",
  "num_adults": 2,
  "num_children": 1,
  "total_amount": 450.00,
  "subtotal_amount": 400.00,
  "tax_amount": 50.00,
  "fee_amount": 0.00,
  "currency_code": "ARS",
  "channel_code": "website_direct",
  "source": "direct",
  "notes": "Requested high floor, sea view"
}
```

**Response (201 Created):**
```json
{
  "id": 1001,
  "confirmation_code": "HOTE20240615ABC",
  "hotel_id": 1,
  "guest_id": 42,
  "guest": {
    "id": 42,
    "first_name": "John",
    "last_name": "Doe",
    "email": "john@example.com"
  },
  "room_id": null,
  "category_id": 3,
  "check_in_date": "2024-06-15",
  "check_out_date": "2024-06-18",
  "actual_check_in": null,
  "actual_check_out": null,
  "num_adults": 2,
  "num_children": 1,
  "nights": 3,
  "total_amount": 450.00,
  "subtotal_amount": 400.00,
  "tax_amount": 50.00,
  "fee_amount": 0.00,
  "commission_amount": 0.00,
  "net_amount": 450.00,
  "deposit_amount": 0.00,
  "amount_paid": 0.00,
  "balance_due": 450.00,
  "currency_code": "ARS",
  "status": "pending",
  "outcome": "pending",
  "guest_segment": "leisure",
  "channel_code": "website_direct",
  "source": "direct",
  "allocation_status": "unassigned",
  "allocation_locked": false,
  "requires_manual_review": false,
  "notes": "Requested high floor, sea view",
  "additional_guests": [],
  "created_at": "2024-06-10T14:30:00Z",
  "updated_at": "2024-06-10T14:30:00Z"
}
```

### 2. List Reservations (with filters)

**Request:**
```bash
GET /api/reservations/?status_filter=pending&from_date=2024-06-01&to_date=2024-06-30&limit=50&offset=0
Authorization: Bearer <token>
```

**Response (200 OK):**
```json
[
  { /* ReservationRead object */ },
  { /* ReservationRead object */ }
]
```

### 3. Assign Room

**Request:**
```bash
POST /api/reservations/1001/assign-room
Authorization: Bearer <token>
Content-Type: application/json

{
  "room_id": 205
}
```

**Response (200 OK):**
```json
{
  "id": 1001,
  "room_id": 205,
  "allocation_status": "assigned",
  "allocation_locked": false,
  "updated_at": "2024-06-10T14:35:00Z",
  ...
}
```

### 4. Record Payment

**Request:**
```bash
POST /api/reservations/1001/mark-paid
Authorization: Bearer <token>
Content-Type: application/json

{
  "amount": 450.00,
  "is_full_payment": true
}
```

**Response (200 OK):**
```json
{
  "id": 1001,
  "status": "fully_paid",
  "amount_paid": 450.00,
  "balance_due": 0.00,
  "updated_at": "2024-06-10T14:40:00Z",
  ...
}
```

### 5. Check In

**Request:**
```bash
POST /api/reservations/1001/check-in
Authorization: Bearer <token>
Content-Type: application/json

{}
```

**Response (200 OK):**
```json
{
  "id": 1001,
  "status": "checked_in",
  "actual_check_in": "2024-06-15T16:25:00Z",
  "updated_at": "2024-06-15T16:25:00Z",
  ...
}
```

### 6. Check Out

**Request:**
```bash
POST /api/reservations/1001/check-out
Authorization: Bearer <token>
Content-Type: application/json

{}
```

**Response (200 OK):**
```json
{
  "id": 1001,
  "status": "checked_out",
  "actual_check_out": "2024-06-18T11:15:00Z",
  "outcome": "completed",
  "updated_at": "2024-06-18T11:15:00Z",
  ...
}
```

### 7. Cancel Reservation

**Request:**
```bash
POST /api/reservations/1001/cancel
Authorization: Bearer <token>
Content-Type: application/json

{
  "reason_code": "guest_request",
  "reason_note": "Guest cancelled due to schedule conflict"
}
```

**Response (200 OK):**
```json
{
  "id": 1001,
  "status": "cancelled",
  "cancelled_at": "2024-06-12T10:00:00Z",
  "cancellation_reason_code": "guest_request",
  "cancellation_reason_note": "Guest cancelled due to schedule conflict",
  "updated_at": "2024-06-12T10:00:00Z",
  ...
}
```

## Error Responses

### 400 Bad Request
```json
{
  "detail": "check_out_date must be after check_in_date"
}
```

### 402 Payment Required
```json
{
  "detail": "Suscripción inactiva. Reactivá el plan para crear nuevas reservas."
}
```

### 404 Not Found
```json
{
  "detail": "Reservation not found"
}
```

### 409 Conflict
```json
{
  "detail": "Room not available for requested dates"
}
```

## Common Query Patterns

### Get pending reservations for next 7 days
```python
from datetime import date, timedelta

today = date.today()
next_week = today + timedelta(days=7)

reservations = list_reservations(
    db=db,
    hotel_id=hotel_id,
    status_filter="pending",
    from_date=today,
    to_date=next_week
)
```

### Find available double rooms for date range
```python
available_rooms = find_available_rooms(
    db=db,
    hotel_id=hotel_id,
    category_id=2,  # Double room
    check_in_date=date(2024, 6, 15),
    check_out_date=date(2024, 6, 18),
    num_adults=2,
    num_children=0
)
```

### Check if specific room is free
```python
is_available = check_room_availability(
    db=db,
    room_id=205,
    check_in_date=date(2024, 6, 15),
    check_out_date=date(2024, 6, 18),
    exclude_reservation_id=None  # Search all
)
```

### Get reservations checked in today
```python
from datetime import date

today = date.today()

reservations = list_reservations(
    db=db,
    hotel_id=hotel_id,
    status_filter="checked_in",
    from_date=today,
    to_date=today
)
```

## Key Business Rules

### State Transitions
- PENDING can go to: DEPOSIT_PAID, FULLY_PAID, CANCELLED
- DEPOSIT_PAID can go to: FULLY_PAID, CANCELLED
- FULLY_PAID can go to: CHECKED_IN, CANCELLED, NO_SHOW
- CHECKED_IN can go to: CHECKED_OUT (only)
- CHECKED_OUT and CANCELLED and NO_SHOW are terminal (cannot transition)

### Check-In Requirements
- Status must be FULLY_PAID
- Room must be assigned (room_id not null)
- Actual date must be >= check_in_date
- Guest capacity must be satisfied

### Check-Out Requirements
- Status must be CHECKED_IN
- Calculate any extra charges (late checkout, damages, etc.)
- Release room back to available pool

### Cancellation Rules
- Cannot cancel after check-in
- Cancellation reasons: guest_request, payment_failure, overbooking, hotel_issue, weather, other
- Process refunds per cancellation policy (% refund, cancellation fee, etc.)
- Release room allocation

### No-Show Rules
- Applied when guest doesn't arrive by some deadline (typically 6pm on check-in day)
- Charge per no-show policy (full, partial, waived)
- Terminal state (cannot check in after marked no-show)

### Room Availability Logic
Dates overlap if:
```
NEW_CHECK_IN < EXISTING_CHECK_OUT AND NEW_CHECK_OUT > EXISTING_CHECK_IN
```

Filter out reservations with statuses: CANCELLED, NO_SHOW (not occupying room)
Keep reservations with statuses: PENDING, DEPOSIT_PAID, FULLY_PAID, CHECKED_IN, CHECKED_OUT (check actual dates)

## Performance Optimization Hints

### Indexes to Create
```sql
CREATE INDEX ix_reservation_hotel_status ON reservations(hotel_id, status);
CREATE INDEX ix_reservation_dates ON reservations(check_in_date, check_out_date);
CREATE INDEX ix_reservation_room_dates ON reservations(room_id, check_in_date, check_out_date);
CREATE INDEX ix_reservation_guest ON reservations(guest_id);
CREATE INDEX ix_reservation_confirmation ON reservations(confirmation_code);
```

### Query Optimization Tips
1. Use eager loading for guest, room, category (frequent access)
2. Use lazy loading for transactions (only load when needed)
3. Filter by hotel_id first to reduce result set
4. Use LIMIT/OFFSET for pagination (don't fetch all rows)
5. Cache hotel configuration (changes infrequently)
6. Cache availability checks (room-date combinations)

### Caching Strategy
- Cache room availability by (room_id, date_range)
- Invalidate cache on reservation state change
- Cache hotel configuration for 24 hours
- Cache room categories and types

## Testing Checklist

```
[ ] Unit Tests
  [ ] Model validations (dates, amounts, counts)
  [ ] Computed properties (nights, balance_due)
  [ ] State machine rules
  
[ ] Service Tests
  [ ] create_reservation with various scenarios
  [ ] list_reservations with all filters
  [ ] update_reservation_fields (allowed vs blocked)
  [ ] transition_reservation_status (valid vs invalid)
  [ ] check_room_availability (overlapping dates)
  [ ] find_available_rooms (capacity, category match)
  [ ] cancel_reservation (refund calculation)
  [ ] perform_checkin/checkout
  
[ ] API Tests
  [ ] POST /api/reservations/ (201 on success, 400 on invalid)
  [ ] GET /api/reservations/ (all filters work)
  [ ] GET /api/reservations/{id} (404 if not found)
  [ ] PATCH /api/reservations/{id} (only safe fields update)
  [ ] DELETE /api/reservations/{id} (403 if already paid)
  [ ] POST /{id}/mark-paid (transitions status)
  [ ] POST /{id}/check-in (validates preconditions)
  [ ] POST /{id}/check-out (finalizes)
  [ ] POST /{id}/cancel (processes refund)
  [ ] POST /{id}/assign-room (checks availability)
  [ ] POST /{id}/extend-stay (recalculates pricing)
  [ ] POST /verify-availability (returns correct rooms)
  
[ ] Authorization Tests
  [ ] Check role requirements per endpoint
  [ ] Verify hotel isolation (can't access other hotel reservations)
  
[ ] Integration Tests
  [ ] Full booking flow: create → assign room → pay → check in → check out
  [ ] Cancellation flow: create → cancel (with refund)
  [ ] No-show flow: create → pay → fully paid → mark no-show
```
