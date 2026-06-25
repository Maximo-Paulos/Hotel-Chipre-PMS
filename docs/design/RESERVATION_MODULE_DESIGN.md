# Reservation Module Design - Complete Skeleton

## Overview
Complete design of the Reservation module including:
- Database models with strict state machine
- Pydantic schemas for API contracts
- CRUD endpoints with role-based access control
- Service layer for business logic
- Error handling and validation

---

## 1. DATABASE MODELS

### 1.1 State Machine

```python
# app/models/reservation.py

# Valid state transitions:
# PENDING → DEPOSIT_PAID → FULLY_PAID → CHECKED_IN → CHECKED_OUT
#        → FULLY_PAID (skip deposit)
#        → CANCELLED (from any pre-checkin state)

class ReservationStatusEnum(str, enum.Enum):
    PENDING = "pending"              # Initial state
    DEPOSIT_PAID = "deposit_paid"    # Partial payment received
    FULLY_PAID = "fully_paid"        # Full payment received
    CHECKED_IN = "checked_in"        # Guest checked in
    CHECKED_OUT = "checked_out"      # Terminal: checkout completed
    CANCELLED = "cancelled"          # Terminal: reservation cancelled
    NO_SHOW = "no_show"             # Terminal: guest did not arrive

class ReservationOutcomeEnum(str, enum.Enum):
    PENDING = "pending"
    CHECKED_IN = "checked_in"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"

# Additional enums for metadata
class ReservationSourceEnum(str, enum.Enum):
    DIRECT = "direct"           # Walk-in or website
    BOOKING = "booking"         # Booking.com
    EXPEDIA = "expedia"         # Expedia
    OTHER_OTA = "other_ota"

class ReservationChannelCodeEnum(str, enum.Enum):
    WEBSITE_DIRECT = "website_direct"
    WHATSAPP = "whatsapp"
    PHONE = "phone"
    WALK_IN = "walk_in"
    BOOKING = "booking"
    EXPEDIA = "expedia"
    DESPEGAR = "despegar"
    OTHER_OTA = "other_ota"
    OTHER_DIRECT = "other_direct"

class ReservationGuestSegmentEnum(str, enum.Enum):
    LEISURE = "leisure"
    BUSINESS = "business"

class ReservationCancellationReasonCodeEnum(str, enum.Enum):
    GUEST_REQUEST = "guest_request"
    PAYMENT_FAILURE = "payment_failure"
    OVERBOOKING = "overbooking"
    HOTEL_ISSUE = "hotel_issue"
    WEATHER = "weather"
    OTHER = "other"
```

### 1.2 Core Reservation Model

```python
class Reservation(Base):
    """
    Core reservation entity.
    Tracks the full lifecycle from booking to checkout.
    
    Relationships:
    - Guest (required, 1:N) - primary guest
    - Room (nullable until assigned)
    - RoomCategory (required for pricing)
    - Company (optional - B2B corporate bookings)
    - SellableProduct (optional - package deals)
    - RatePlan (optional - pricing model)
    - Transactions (1:N) - payments/refunds
    """
    __tablename__ = "reservations"

    # Primary key & identification
    id: Integer (PK, autoincrement)
    confirmation_code: String(30) (unique, indexed)
    hotel_id: Integer (FK → hotel_configuration.id, required)

    # Guest and Room linkage
    guest_id: Integer (FK → guests.id, required)
    room_id: Integer (FK → rooms.id, nullable until assigned)
    category_id: Integer (FK → room_categories.id, required)
    company_id: Integer (FK → companies.id, nullable)
    sellable_product_id: Integer (FK → sellable_products.id, nullable)
    rate_plan_id: Integer (FK → rate_plans.id, nullable)
    tax_policy_id: Integer (FK → tax_policies.id, nullable)

    # Stay dates
    check_in_date: Date (required)
    check_out_date: Date (required, > check_in_date)
    actual_check_in: DateTime (nullable - filled on checkin)
    actual_check_out: DateTime (nullable - filled on checkout)
    arrival_time_hint: String(80) (nullable - guest preference)

    # Financial tracking
    total_amount: Float (>= 0, ARS currency)
    subtotal_amount: Float (before tax/fees)
    tax_amount: Float (calculated from tax_policy)
    fee_amount: Float (processing fees)
    commission_amount: Float (OTA commission if applicable)
    net_amount: Float (amount hotel receives)
    deposit_amount: Float (initial payment required)
    amount_paid: Float (cumulative payments, >= 0)
    currency_code: String(3) (default "ARS")
    fx_rate_snapshot: Float (nullable - for FX conversions)

    # State machine & outcomes
    status: Enum(ReservationStatusEnum, default=PENDING)
    outcome: Enum(ReservationOutcomeEnum, default=PENDING)
    guest_segment: Enum(ReservationGuestSegmentEnum, default=LEISURE)
    guest_segment_source: Enum(ReservationGuestSegmentSourceEnum)
    channel_code: Enum(ReservationChannelCodeEnum)

    # Cancellation tracking
    cancelled_at: DateTime (nullable)
    cancelled_by_user_id: Integer (FK → users.id, nullable)
    cancellation_reason_code: Enum(ReservationCancellationReasonCodeEnum, nullable)
    cancellation_reason_note: String(500, nullable)

    # No-show tracking
    no_show_confirmed_at: DateTime (nullable)
    no_show_policy_applied: Enum(ReservationNoShowPolicyAppliedEnum)

    # OTA integration
    source: Enum(ReservationSourceEnum, default=DIRECT)
    source_provider_code: String(50, indexed, nullable) - e.g., "booking_12345"
    external_id: String(100, indexed, nullable) - OTA booking ID
    external_confirmation_code: String(120, nullable)
    
    # Room assignment state
    allocation_status: String(30) - "unassigned", "assigned", "locked"
    allocation_locked: Boolean (prevents room changes after payment)
    requires_manual_review: Boolean (flag for staff action needed)

    # Metadata
    num_adults: Integer (> 0)
    num_children: Integer (>= 0)
    notes: Text (nullable - staff/guest notes)
    requested_attributes_json: Text (nullable - special requests)
    pricing_snapshot: Text (nullable - original pricing at booking time)
    payment_collection_model: String(40) - "hotel_collect", "ota_collect"
    settlement_status: String(40) - OTA settlement tracking

    created_at: DateTime (auto, UTC)
    updated_at: DateTime (auto-update, UTC)

    # Relationships
    guest: Guest (eager-loaded)
    additional_guests: List[Guest] (many-to-many via reservation_additional_guests)
    room: Room (eager-loaded)
    category: RoomCategory
    sellable_product: SellableProduct
    rate_plan: RatePlan
    tax_policy: TaxPolicy
    transactions: List[Transaction] (cascade delete)

    # Computed properties
    @property
    nights: int = (check_out_date - check_in_date).days
    
    @property
    balance_due: float = max(0.0, total_amount - amount_paid)

    # Business logic
    def can_transition_to(new_status: ReservationStatusEnum) -> bool:
        """Validate state transitions per the state machine"""
        
    def can_be_cancelled() -> bool:
        """Check if cancellation is allowed (not checked-in/out)"""
        
    def can_be_checked_in() -> bool:
        """Check: status=FULLY_PAID, today >= check_in_date"""
        
    def can_be_checked_out() -> bool:
        """Check: status=CHECKED_IN"""

    # Constraints
    __table_args__ = (
        CheckConstraint("check_out_date > check_in_date"),
        CheckConstraint("total_amount >= 0"),
        CheckConstraint("amount_paid >= 0"),
        CheckConstraint("amount_paid <= total_amount"),
        CheckConstraint("num_adults > 0"),
        CheckConstraint("num_children >= 0"),
        Index("ix_reservation_dates", "check_in_date", "check_out_date"),
        Index("ix_reservation_hotel_id", "hotel_id"),
        Index("ix_reservation_guest_id", "guest_id"),
        Index("ix_reservation_room_id", "room_id"),
        Index("ix_reservation_status", "status"),
        Index("ix_reservation_external_id", "external_id"),
    )
```

### 1.3 Many-to-Many Association

```python
# In reservation.py
reservation_additional_guests = Table(
    "reservation_additional_guests",
    Base.metadata,
    Column("reservation_id", Integer, FK("reservations.id", ondelete="CASCADE"), PK),
    Column("guest_id", Integer, FK("guests.id", ondelete="CASCADE"), PK)
)
```

---

## 2. PYDANTIC SCHEMAS

### 2.1 Base Schemas

```python
# app/schemas/reservation.py

class ReservationBase(BaseModel):
    """Common fields for all reservation operations"""
    check_in_date: date
    check_out_date: date
    arrival_time_hint: str | None = None
    num_adults: int = 1  # >= 1
    num_children: int = 0  # >= 0
    notes: str | None = None
    requested_attributes_json: str | None = None
    guest_segment: ReservationGuestSegmentEnum = LEISURE
    channel_code: ReservationChannelCodeEnum


class ReservationCreate(ReservationBase):
    """Input for POST /reservations"""
    guest_id: int
    category_id: int
    room_id: int | None = None  # Nullable until assigned
    company_id: int | None = None
    rate_plan_id: int | None = None
    deposit_amount: float = 0.0
    total_amount: float
    subtotal_amount: float
    tax_amount: float = 0.0
    fee_amount: float = 0.0
    currency_code: str = "ARS"
    source: ReservationSourceEnum = DIRECT
    source_provider_code: str | None = None
    external_id: str | None = None
    external_confirmation_code: str | None = None
    payment_collection_model: str = "hotel_collect"

    @field_validator("check_out_date")
    def validate_dates(cls, v, info):
        if v <= info.data.get("check_in_date"):
            raise ValueError("check_out_date must be after check_in_date")
        return v

    @field_validator("num_adults")
    def validate_adults(cls, v):
        if v < 1:
            raise ValueError("at least 1 adult required")
        return v

    @field_validator("total_amount", "subtotal_amount", "tax_amount")
    def validate_amounts(cls, v):
        if v < 0:
            raise ValueError("amounts cannot be negative")
        return v


class ReservationUpdate(BaseModel):
    """Input for PATCH /reservations/{id}"""
    # Only allow non-critical updates
    arrival_time_hint: str | None = None
    notes: str | None = None
    num_adults: int | None = None
    num_children: int | None = None
    requested_attributes_json: str | None = None
    guest_segment: ReservationGuestSegmentEnum | None = None


class ReservationStatusTransition(BaseModel):
    """Input for status change operations"""
    new_status: ReservationStatusEnum
    reason: str | None = None  # e.g., cancellation reason


class ReservationRead(ReservationBase):
    """Output for GET endpoints"""
    id: int
    confirmation_code: str
    hotel_id: int
    guest_id: int
    guest: GuestRead
    room_id: int | None
    category_id: int
    company_id: int | None
    rate_plan_id: int | None
    actual_check_in: datetime | None
    actual_check_out: datetime | None
    
    # Financial
    total_amount: float
    subtotal_amount: float
    tax_amount: float
    fee_amount: float
    commission_amount: float
    net_amount: float
    deposit_amount: float
    amount_paid: float
    balance_due: float  # Computed
    currency_code: str
    
    # State
    status: ReservationStatusEnum
    outcome: ReservationOutcomeEnum
    guest_segment_source: ReservationGuestSegmentSourceEnum
    
    # OTA
    source: ReservationSourceEnum
    source_provider_code: str | None
    external_id: str | None
    external_confirmation_code: str | None
    
    # Cancellation
    cancelled_at: datetime | None
    cancelled_by_user_id: int | None
    cancellation_reason_code: ReservationCancellationReasonCodeEnum | None
    cancellation_reason_note: str | None
    
    # Room assignment
    allocation_status: str
    allocation_locked: bool
    requires_manual_review: bool
    
    # Computed
    nights: int
    additional_guests: list[dict]  # [{"id", "first_name", "last_name", ...}]
    
    created_at: datetime
    updated_at: datetime
    
    class Config:
        from_attributes = True


class ReservationListFilters(BaseModel):
    """Query parameters for list endpoint"""
    status_filter: str = ""  # "pending", "checked_in", etc. or empty for all
    from_date: date | None = None
    to_date: date | None = None
    guest_id: int | None = None
    room_id: int | None = None
    category_id: int | None = None
    source: ReservationSourceEnum | None = None
    search_text: str | None = None  # Search in confirmation_code, guest name
    limit: int = 100
    offset: int = 0
```

---

## 3. SERVICE LAYER

### 3.1 Main Reservation Service

```python
# app/services/reservation_service.py

class ReservationError(Exception):
    """Base exception for reservation operations"""
    pass


class ReservationNotFoundError(ReservationError):
    pass


class InvalidStateTransitionError(ReservationError):
    pass


class InsufficientPaymentError(ReservationError):
    pass


class RoomNotAvailableError(ReservationError):
    pass


def create_reservation(
    db: Session,
    data: ReservationCreate,
    hotel_id: int,
    generated_confirmation_code: str | None = None
) -> Reservation:
    """
    Create a new reservation.
    
    Logic:
    1. Validate guest exists and belongs to hotel
    2. Validate room category exists
    3. Check room availability if room_id provided
    4. Generate unique confirmation_code if not provided
    5. Create Reservation record
    6. Emit "reservation.created" event
    
    Returns: Reservation
    Raises: ReservationError
    """
    pass


def get_reservation_by_id(db: Session, reservation_id: int, hotel_id: int) -> Reservation:
    """
    Fetch single reservation with hotel-scope isolation.
    
    Raises: ReservationNotFoundError
    """
    pass


def list_reservations(
    db: Session,
    hotel_id: int,
    status_filter: str = "",
    from_date: date | None = None,
    to_date: date | None = None,
    guest_id: int | None = None,
    room_id: int | None = None,
    category_id: int | None = None,
    source: ReservationSourceEnum | None = None,
    search_text: str | None = None,
    limit: int = 100,
    offset: int = 0
) -> tuple[list[Reservation], int]:
    """
    List reservations with filtering and pagination.
    
    Returns: (reservations, total_count)
    """
    pass


def update_reservation_fields(
    db: Session,
    reservation_id: int,
    hotel_id: int,
    data: ReservationUpdate
) -> Reservation:
    """
    Update non-critical fields.
    
    Allowed: arrival_time_hint, notes, guest_segment
    Blocked: dates, amounts, status transitions
    
    Raises: ReservationNotFoundError, ReservationError
    """
    pass


def transition_reservation_status(
    db: Session,
    reservation_id: int,
    hotel_id: int,
    new_status: ReservationStatusEnum,
    reason: str | None = None,
    user_id: int | None = None
) -> Reservation:
    """
    Transition reservation state with business rule validation.
    
    Validates:
    - State machine rules (VALID_TRANSITIONS)
    - Financial preconditions (e.g., FULLY_PAID before CHECKED_IN)
    - Room assignment (CHECKED_IN requires room_id)
    - Cancellation eligibility
    
    Side effects:
    - Update status, outcome, cancelled_at, timestamps
    - Emit "reservation.status_changed" event
    - If cancelled: release room allocation, process refunds
    
    Raises: InvalidStateTransitionError, ReservationError
    """
    pass


def check_room_availability(
    db: Session,
    room_id: int,
    check_in_date: date,
    check_out_date: date,
    exclude_reservation_id: int | None = None
) -> bool:
    """
    Check if a specific room is available for date range.
    
    Considers:
    - Other non-cancelled reservations overlapping dates
    - Room maintenance blocks
    - Room status (operational vs. out-of-order)
    
    Returns: True if available
    """
    pass


def find_available_rooms(
    db: Session,
    hotel_id: int,
    category_id: int,
    check_in_date: date,
    check_out_date: date,
    num_adults: int,
    num_children: int
) -> list[Room]:
    """
    Find all available rooms matching category for date range.
    
    Filters:
    - Room capacity >= guests
    - No overlapping reservations
    - Room operational
    
    Returns: list[Room] sorted by room_number
    """
    pass


def cancel_reservation(
    db: Session,
    reservation_id: int,
    hotel_id: int,
    reason_code: ReservationCancellationReasonCodeEnum,
    reason_note: str | None = None,
    user_id: int | None = None
) -> Reservation:
    """
    Cancel a reservation.
    
    Constraints:
    - Cannot cancel checked-in/checked-out reservations
    - Processes refunds based on cancellation policy
    - Releases room allocation
    - Records cancellation metadata
    
    Raises: ReservationError (if cannot cancel)
    """
    pass


def extend_stay(
    db: Session,
    reservation_id: int,
    hotel_id: int,
    new_check_out_date: date
) -> Reservation:
    """
    Extend check_out_date and recalculate pricing.
    
    Constraints:
    - Only for checked-in reservations
    - Must verify room availability for extra nights
    - Recalculate amount_due
    
    Raises: ReservationError
    """
    pass


def perform_checkin(
    db: Session,
    reservation_id: int,
    hotel_id: int
) -> Reservation:
    """
    Perform check-in (update actual_check_in, status → CHECKED_IN).
    
    Preconditions:
    - status == FULLY_PAID
    - actual_check_in_date >= check_in_date
    - room_id assigned
    
    Side effects:
    - Update actual_check_in timestamp
    - Transition status to CHECKED_IN
    - Emit "reservation.checked_in" event
    
    Raises: ReservationError
    """
    pass


def perform_checkout(
    db: Session,
    reservation_id: int,
    hotel_id: int
) -> Reservation:
    """
    Perform check-out (update actual_check_out, status → CHECKED_OUT).
    
    Preconditions:
    - status == CHECKED_IN
    
    Side effects:
    - Update actual_check_out timestamp
    - Transition status to CHECKED_OUT
    - Emit "reservation.checked_out" event
    - Calculate final charges/refunds
    
    Raises: ReservationError
    """
    pass
```

---

## 4. API ENDPOINTS

### 4.1 CRUD Endpoints

```
POST   /api/reservations/
       Create new reservation
       Input: ReservationCreate
       Output: ReservationRead (201 Created)
       Auth: owner, co_owner, manager, housekeeping
       Validation:
         - Guest must exist and belong to hotel
         - Dates must be in future (or at least today)
         - Amounts must be positive
         - Room category must exist
       Errors:
         - 400: Invalid input, room not available, guest not found
         - 402: Subscription inactive
         - 403: Unauthorized role


GET    /api/reservations/
       List reservations with filtering
       Query params:
         - status_filter: "" | "pending" | "checked_in" | "cancelled" | ...
         - from_date: YYYY-MM-DD (optional)
         - to_date: YYYY-MM-DD (optional)
         - guest_id: int (optional)
         - room_id: int (optional)
         - search_text: string (optional - search code/guest name)
         - limit: int = 100
         - offset: int = 0
       Output: list[ReservationRead]
       Auth: Any authenticated user (hotel-scoped)
       Errors:
         - 400: Invalid date range
         - 403: Unauthorized


GET    /api/reservations/{id}
       Get single reservation
       Output: ReservationRead
       Auth: Any authenticated user (hotel-scoped)
       Errors:
         - 404: Not found
         - 403: Not in user's hotel


PATCH  /api/reservations/{id}
       Update reservation (non-critical fields only)
       Input: ReservationUpdate
       Output: ReservationRead
       Auth: manager, owner, co_owner
       Allowed changes:
         - arrival_time_hint
         - notes
         - guest_segment
       Blocked changes:
         - dates, amounts, status, room_id
       Errors:
         - 400: Invalid update
         - 404: Not found
         - 403: Unauthorized


DELETE /api/reservations/{id}
       Delete reservation (only if status=PENDING and not yet allocated)
       Output: 204 No Content
       Auth: owner, co_owner, manager
       Constraints:
         - Cannot delete if payment received
         - Cannot delete if room allocated and allocation_locked
       Errors:
         - 400: Cannot delete (wrong status, already paid)
         - 404: Not found
         - 403: Unauthorized
```

### 4.2 State Transition Endpoints

```
POST   /api/reservations/{id}/mark-paid
       Transition PENDING → DEPOSIT_PAID or FULLY_PAID
       Input: {amount: float, is_full_payment: bool}
       Output: ReservationRead
       Auth: owner, co_owner, manager, accountant
       Business logic:
         - Validates amount >= deposit_amount
         - Creates Transaction record
         - If is_full_payment: moves to FULLY_PAID
         - Otherwise: moves to DEPOSIT_PAID
       Errors:
         - 400: Invalid amount, wrong status
         - 404: Not found


POST   /api/reservations/{id}/check-in
       Transition FULLY_PAID → CHECKED_IN
       Input: {} (optional: arrival_time, notes)
       Output: ReservationRead
       Auth: housekeeping, manager, owner
       Preconditions:
         - status == FULLY_PAID
         - room_id must be assigned
         - today >= check_in_date
       Errors:
         - 400: Not ready for check-in
         - 404: Not found


POST   /api/reservations/{id}/check-out
       Transition CHECKED_IN → CHECKED_OUT
       Input: {} (optional: departure_notes)
       Output: ReservationRead
       Auth: housekeeping, manager, owner
       Preconditions:
         - status == CHECKED_IN
       Side effects:
         - Final damage/service charges applied if any
       Errors:
         - 400: Not checked in
         - 404: Not found


POST   /api/reservations/{id}/cancel
       Transition to CANCELLED (from PENDING, DEPOSIT_PAID, FULLY_PAID)
       Input: {reason_code: string, reason_note: string, user_id: int}
       Output: ReservationRead
       Auth: owner, co_owner, manager
       Constraints:
         - Cannot cancel after CHECKED_IN
         - Processes refunds per cancellation policy
         - Releases room allocation
       Errors:
         - 400: Cannot cancel (wrong status)
         - 404: Not found


POST   /api/reservations/{id}/mark-no-show
       Transition FULLY_PAID → NO_SHOW (after check-in time passes)
       Input: {policy_applied: string}  # "none", "full_charge", "partial_charge", "waived"
       Output: ReservationRead
       Auth: manager, owner
       Business logic:
         - Applies no-show fee per hotel config
         - Marks outcome as NO_SHOW
       Errors:
         - 400: Wrong status
         - 404: Not found
```

### 4.3 Advanced Operations

```
POST   /api/reservations/{id}/assign-room
       Assign a room to reservation (before check-in)
       Input: {room_id: int}
       Output: ReservationRead
       Auth: manager, owner
       Validation:
         - Room must be available for date range
         - Reservation status must allow (not CHECKED_IN or later)
         - Room category must match or be compatible
       Errors:
         - 400: Room not available, incompatible
         - 404: Room or reservation not found


POST   /api/reservations/{id}/move-room
       Move checked-in guest to different room (housekeeping)
       Input: {target_room_id: int, reason: string}
       Output: ReservationRead
       Auth: housekeeping, manager
       Preconditions:
         - status == CHECKED_IN
         - Target room available/clean
       Side effects:
         - Releases old room
         - Assigns new room
         - Logs room move reason
       Errors:
         - 400: Cannot move (not checked-in, target unavailable)


POST   /api/reservations/{id}/extend-stay
       Extend check-out date
       Input: {new_check_out_date: date}
       Output: ReservationRead
       Auth: manager, owner
       Validation:
         - status must be CHECKED_IN or FULLY_PAID
         - Room must be available for extra nights
         - Recalculates total_amount
       Errors:
         - 400: Cannot extend (wrong status, room not available)


POST   /api/reservations/verify-availability
       Batch check room availability for date range
       Input: {
         category_id: int,
         check_in_date: date,
         check_out_date: date,
         num_adults: int,
         num_children: int
       }
       Output: {available_rooms: list[RoomRead]}
       Auth: Any authenticated user
       Errors:
         - 400: Invalid input


GET    /api/reservations/{id}/timeline
       Get timeline of status changes and events
       Output: {events: list[{timestamp, status, reason, user}]}
       Auth: Any authenticated user (hotel-scoped)
       Errors:
         - 404: Not found
```

---

## 5. ERROR HANDLING

### Custom Exceptions

```python
# app/services/reservation_service.py

class ReservationError(Exception):
    """Base exception"""

class ReservationNotFoundError(ReservationError):
    """Reservation with given ID not found"""

class InvalidStateTransitionError(ReservationError):
    """State transition violates state machine"""

class InsufficientPaymentError(ReservationError):
    """Payment amount insufficient"""

class RoomNotAvailableError(ReservationError):
    """Room not available for date range"""

class RoomNotAssignedError(ReservationError):
    """Room must be assigned before operation"""

class UnauthorizedOperationError(ReservationError):
    """User cannot perform this operation on this reservation"""

class InvalidDateRangeError(ReservationError):
    """Dates invalid (check_out <= check_in, past dates, etc.)"""
```

### HTTP Error Responses

```python
# In FastAPI routes:

@router.post("/")
def create_new_reservation(...):
    try:
        reservation = create_reservation(db, data, hotel_id)
    except ReservationError as e:
        raise HTTPException(status_code=400, detail=str(e))
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        raise HTTPException(status_code=500, detail="Internal server error")


# Common patterns:
400 Bad Request       - Validation failed, state machine violation, dates invalid
402 Payment Required  - Subscription inactive
403 Forbidden         - User lacks role, wrong hotel
404 Not Found         - Reservation/guest/room not found
409 Conflict          - Room unavailable, state conflict
500 Internal Error    - Unexpected server error
```

---

## 6. VALIDATION & CONSTRAINTS

### Date Validations

```python
def validate_reservation_dates(check_in: date, check_out: date):
    """
    - check_out > check_in
    - check_in >= today (for direct bookings)
    - check_in < check_out + 365 days (no multi-year bookings)
    """

def validate_historical_operations(res: Reservation):
    """
    - Cannot modify CHECKED_OUT or CANCELLED reservations
    - Cannot re-open check-in after check-out
    """
```

### Room Assignment Constraints

```python
def validate_room_assignment(res: Reservation, room: Room):
    """
    - Room capacity >= num_adults + num_children
    - Room category matches reservation category_id
    - Room available for entire stay
    - Room operational (not maintenance, not out-of-order)
    """
```

### Financial Validations

```python
def validate_payment(res: Reservation, payment_amount: float):
    """
    - payment_amount > 0
    - payment_amount <= total_amount (no overpayment)
    - total_amount >= subtotal_amount + tax_amount
    """
```

---

## 7. RELATIONSHIPS DIAGRAM

```
┌──────────────────────────────┐
│      Reservation             │
│  (core booking entity)       │
│                              │
│  id, confirmation_code       │
│  status, outcome             │
│  check_in_date, check_out    │
│  total_amount, amount_paid   │
└──────────────────────────────┘
         │                  │
         │ (1:1)           │ (1:1)
         ▼                  ▼
    ┌────────┐         ┌────────┐
    │ Guest  │         │ Room   │
    │ (PK)   │         │ (PK)   │
    └────────┘         └────────┘
         │
         │ (1:N via M2M)
         ▼
    ┌──────────────────────┐
    │ Additional Guests    │
    │ (secondary occupants)│
    └──────────────────────┘


┌──────────────────────────────┐
│      Reservation             │
└──────────────────────────────┘
    │ (1:1)           │ (1:1)       │ (1:1)
    ▼                 ▼             ▼
┌─────────────┐ ┌──────────────┐ ┌──────────┐
│RoomCategory │ │RatePlan      │ │TaxPolicy │
│(pricing cat)│ │(rate calc)   │ │(tax calc)│
└─────────────┘ └──────────────┘ └──────────┘

┌──────────────────────────────┐
│      Reservation             │
└──────────────────────────────┘
    │ (1:N)                   │ (1:N)
    ▼                         ▼
┌──────────────┐        ┌──────────────────┐
│ Transaction  │        │OperationalEvent  │
│(payments)    │        │(room moves, etc.)│
└──────────────┘        └──────────────────┘
```

---

## 8. IMPLEMENTATION CHECKLIST

### Phase 1: Core Models & Schemas (Foundation)
- [ ] Finalize ReservationStatusEnum and state machine rules
- [ ] Implement Reservation ORM model
- [ ] Create reservation_additional_guests association table
- [ ] Define Pydantic schemas (Create, Read, Update)
- [ ] Write unit tests for model validations and computed properties

### Phase 2: Service Layer (Business Logic)
- [ ] Implement create_reservation with confirmation code generation
- [ ] Implement list_reservations with all filters
- [ ] Implement update_reservation_fields (safe updates only)
- [ ] Implement transition_reservation_status with state machine validation
- [ ] Implement check_room_availability
- [ ] Implement find_available_rooms
- [ ] Implement cancel_reservation with refund logic
- [ ] Write comprehensive service tests

### Phase 3: API Endpoints (HTTP Routes)
- [ ] POST /api/reservations/ - Create
- [ ] GET /api/reservations/ - List with filters
- [ ] GET /api/reservations/{id} - Get single
- [ ] PATCH /api/reservations/{id} - Update
- [ ] DELETE /api/reservations/{id} - Delete (soft-delete)
- [ ] POST /api/reservations/{id}/mark-paid
- [ ] POST /api/reservations/{id}/check-in
- [ ] POST /api/reservations/{id}/check-out
- [ ] POST /api/reservations/{id}/cancel
- [ ] POST /api/reservations/{id}/mark-no-show
- [ ] Write endpoint integration tests

### Phase 4: Advanced Features
- [ ] POST /api/reservations/{id}/assign-room
- [ ] POST /api/reservations/{id}/move-room
- [ ] POST /api/reservations/{id}/extend-stay
- [ ] POST /api/reservations/verify-availability (batch)
- [ ] GET /api/reservations/{id}/timeline
- [ ] Event logging and audit trail
- [ ] OTA synchronization hooks

### Phase 5: Frontend & Testing
- [ ] Frontend React components for reservation CRUD
- [ ] End-to-end tests
- [ ] Performance optimization (query optimization, caching)
- [ ] Documentation & API spec generation
