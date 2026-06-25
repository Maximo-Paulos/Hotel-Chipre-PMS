# Check-in Module Design — Flow, Validations & Blocks

## Overview
The Hotel Chipre PMS Check-in module manages the guest arrival workflow from reservation to occupied room. It enforces a strict validation gate before physical check-in can occur, integrating jurisdiction profiles (AR/UY/CL), payment verification, document validation, and legal compliance.

---

## Core Flow Diagram

```
┌─────────────────────────────────────────────────────────────────┐
│ RESERVATION STATE MACHINE (Pre-Checkin)                          │
│                                                                  │
│  PENDING ──► DEPOSIT_PAID ──► FULLY_PAID ──► [CHECKIN GATE]    │
│                               (skip)        │                   │
│                                             ├─► CHECKED_IN      │
│                                             │                   │
│                                             └─► CHECKED_OUT     │
└─────────────────────────────────────────────────────────────────┘

                ↓
        ┌───────────────────────────────────────────────────┐
        │ CHECKIN VALIDATION GATE                            │
        │                                                    │
        │ 1. Verify FULLY_PAID status                       │
        │ 2. Load guest & jurisdiction profile              │
        │ 3. Validate guest required fields                 │
        │ 4. Check room availability                        │
        │ 5. Generate/verify check-in document              │
        │ 6. Record actual check-in timestamp               │
        │ 7. Transition to CHECKED_IN                       │
        │ 8. Mark room as OCCUPIED                          │
        └───────────────────────────────────────────────────┘
                ↓
        ┌───────────────────────────────────────────────────┐
        │ CHECKED_IN STATE                                   │
        │ • Room occupied for housekeeping                  │
        │ • Guest can request services                      │
        │ • Upsell/extras available                         │
        │ • Can proceed to checkout                         │
        └───────────────────────────────────────────────────┘
```

---

## Validation Blocks (Sequential)

### Block 1: Reservation Status Verification
**Purpose:** Ensure reservation is in valid state for check-in  
**Conditions:**
- Status must be `FULLY_PAID` (or `CHECKED_IN` for idempotent re-entry)
- Reservation must not be `CANCELLED`, `NO_SHOW`, or `CHECKED_OUT`
- Reservation must exist and belong to the hotel

**Error Responses:**
```
BlockCheckError(
  code="invalid_reservation_status",
  message=f"Cannot check in: status is '{current}'. Must be 'fully_paid'",
  current_status=reservation.status,
  expected_status="fully_paid",
  balance_due=reservation.balance_due
)
```

### Block 2: Guest Record Existence & Scope
**Purpose:** Verify guest record exists and belongs to hotel

**Conditions:**
- Guest exists with `guest_id` matching reservation
- Guest belongs to same `hotel_id` as reservation
- Guest is not soft-deleted

**Error Responses:**
```
BlockCheckError(
  code="guest_not_found",
  message="Guest record not found for this reservation",
  guest_id=reservation.guest_id,
  hotel_id=context.hotel_id
)
```

### Block 3: Guest Data Completeness (Jurisdiction-Aware)
**Purpose:** Validate all required guest fields per jurisdiction profile

**Logic:**
```python
profile = get_profile(jurisdiction_code)  # AR | UY | CL
required_fields = ["first_name", "last_name"]

if require_document:
    required_fields.extend(profile.document_fields)
    required_fields.extend(profile.extra_required_fields)

if require_terms and profile.requires_terms_acceptance:
    must_have_terms_accepted = True
```

**Jurisdiction Profiles:**

| Code | Doc Fields | Extra Fields | Req. Terms | Status |
|------|-----------|------------|-----------|--------|
| **AR** | DNI, PASSPORT, CEDULA | none | yes | Launch-Active |
| **UY** | DNI, PASSPORT, CEDULA | nationality | yes | Experimental |
| **CL** | DNI, PASSPORT, CEDULA | nationality, country | yes | Experimental |

**Error Responses:**
```
BlockCheckError(
  code="missing_guest_fields",
  message="Check-in blocked — missing required guest data",
  missing_fields=[
    "First name is required",
    "Document type (DNI/Passport) is required",
    "Guest must accept terms and conditions"
  ],
  jurisdiction_code="AR"
)
```

### Block 4: Document Validation (AR-Specific)
**Purpose:** Validate identity document format and integrity

**For Argentina:**
- DNI: 8 digits (format: XX.XXX.XXX)
- CUIT: 11 digits (format: XX-XXXXXXXX-X)
- Passport: 6-9 alphanumeric

**Error Responses:**
```
BlockCheckError(
  code="invalid_document_format",
  message="Document number format invalid for DNI",
  document_type="DNI",
  document_number="invalid",
  expected_format="8 digits (XX.XXX.XXX)"
)
```

### Block 5: Room Availability Check
**Purpose:** Verify assigned room is available and ready

**Conditions:**
- Room exists and belongs to hotel
- Room status is `READY` or `AVAILABLE`
- Room has not been assigned to another guest for overlapping period
- Room category matches reservation room category (if enforced)

**Error Responses:**
```
BlockCheckError(
  code="room_unavailable",
  message=f"Room {room_id} is not available for check-in",
  room_id=reservation.room_id,
  room_status=room.status,
  expected_status="ready"
)
```

### Block 6: Check-in Document Generation & Verification
**Purpose:** Generate/verify legal check-in documentation

**Generates:**
- Guest registration form (jurisdictionally-specific)
- Digital signature capture (with timestamp)
- Terms acceptance record
- Room assignment confirmation

**Error Responses:**
```
BlockCheckError(
  code="document_generation_failed",
  message="Could not generate check-in documentation",
  reason="template_missing_for_jurisdiction_AR"
)
```

---

## Validation Rules & Blocks Summary

| Priority | Block | Input | Output | Failure Mode |
|----------|-------|-------|--------|--------------|
| 1 | Reservation Status | reservation_id, hotel_id | valid_reservation | 400 invalid_status |
| 2 | Guest Existence | guest_id, hotel_id | guest_record | 404 not_found |
| 3 | Guest Data | guest, jurisdiction | missing_fields[] | 422 incomplete_data |
| 4 | Document Format | document_type, document_number | valid_document | 422 invalid_format |
| 5 | Room Availability | room_id, dates | available_room | 409 unavailable |
| 6 | Check-in Doc | jurisdiction_code, guest | signed_document | 500 doc_generation |

---

## Endpoint Specifications

### 1. POST /api/checkin/{reservation_id}
**Purpose:** Perform full check-in with all validations

**Request:**
```json
{
  "reservation_id": 123,
  "digital_signature": "data:image/png;base64,iVBORw0K...",
  "signature_timestamp": "2025-06-09T14:30:00Z",
  "accept_terms": true
}
```

**Response (200):**
```json
{
  "id": 123,
  "guest_id": 45,
  "guest": {
    "id": 45,
    "first_name": "Juan",
    "last_name": "Pérez",
    "document_type": "DNI",
    "document_number": "12345678",
    "terms_accepted": true
  },
  "room_id": 301,
  "status": "checked_in",
  "actual_check_in": "2025-06-09T14:30:00Z",
  "balance_due": 0.00,
  "nights": 3
}
```

**Error Responses:**
- `400` — Invalid reservation status
- `404` — Reservation or guest not found
- `409` — Room unavailable
- `422` — Missing required guest fields
- `500` — Document generation failed

**Flow:**
```
1. Load reservation + guest + room
2. Run validation blocks 1-6
3. Record actual_check_in timestamp
4. Update reservation.status = CHECKED_IN
5. Update room.status = OCCUPIED
6. Commit & return
```

---

### 2. GET /api/checkin/validate/{reservation_id}
**Purpose:** Pre-flight validation (no state changes) — check what will pass/fail

**Response (200):**
```json
{
  "reservation_id": 123,
  "can_check_in": true,
  "blocks": [
    {
      "block_id": "reservation_status",
      "status": "pass",
      "message": "Reservation status is fully_paid"
    },
    {
      "block_id": "guest_existence",
      "status": "pass",
      "message": "Guest record found"
    },
    {
      "block_id": "guest_data_completeness",
      "status": "fail",
      "message": "Missing required fields",
      "missing_fields": ["Document type is required"],
      "jurisdiction_code": "AR"
    },
    {
      "block_id": "document_format",
      "status": "skip",
      "message": "Document field not provided yet"
    },
    {
      "block_id": "room_availability",
      "status": "pass",
      "message": "Room 301 is ready"
    },
    {
      "block_id": "checkin_document",
      "status": "pending",
      "message": "Document will be generated on check-in"
    }
  ],
  "blocking_issues": [
    {
      "block_id": "guest_data_completeness",
      "field": "document_type",
      "message": "Document type (DNI/Passport) is required for AR"
    }
  ]
}
```

---

### 3. POST /api/checkin/{reservation_id}/validate-guest
**Purpose:** Validate specific guest data before full check-in

**Request:**
```json
{
  "guest_id": 45,
  "updates": {
    "document_type": "DNI",
    "document_number": "12345678",
    "terms_accepted": true
  }
}
```

**Response (200):**
```json
{
  "guest_id": 45,
  "valid": true,
  "missing_fields": [],
  "validation_blocks": [
    {
      "field": "first_name",
      "status": "pass",
      "value": "Juan"
    },
    {
      "field": "document_type",
      "status": "pass",
      "value": "DNI"
    },
    {
      "field": "document_number",
      "status": "pass",
      "value": "12345678",
      "format_valid": true,
      "format": "AR_DNI"
    },
    {
      "field": "terms_accepted",
      "status": "pass",
      "value": true
    }
  ]
}
```

---

### 4. POST /api/checkin/{reservation_id}/document
**Purpose:** Generate/download check-in registration document (PDF)

**Query Params:**
```
?format=pdf|html&locale=es-AR
```

**Response (200):**
```
Content-Type: application/pdf
Content-Disposition: attachment; filename="checkin-R123-20250609.pdf"

[PDF binary content]
```

**PDF Structure:**
```
┌───────────────────────────────────┐
│ HOTEL CHIPRE - CHECK-IN FORM      │
│ Registration #: 123               │
│ Date: 2025-06-09                  │
├───────────────────────────────────┤
│ GUEST INFORMATION                 │
│ Name: Juan Pérez                  │
│ DNI: 12.345.678                   │
│ Nationality: Argentina            │
├───────────────────────────────────┤
│ ROOM ASSIGNMENT                   │
│ Room: 301                          │
│ Check-in: 2025-06-09 14:30:00     │
│ Check-out: 2025-06-12 11:00:00    │
├───────────────────────────────────┤
│ HOUSE RULES & TERMS               │
│ ☑ Accept terms and conditions     │
│ ☑ Accept privacy policy           │
├───────────────────────────────────┤
│ SIGNATURE                          │
│ _____________________  2025-06-09 │
│ Guest Signature       Date        │
└───────────────────────────────────┘
```

---

### 5. POST /api/checkin/{reservation_id}/checkout
**Purpose:** Check out reservation and mark room for cleaning

**Request:**
```json
{
  "reservation_id": 123,
  "checkout_notes": "Room was clean, guest left keys at desk"
}
```

**Response (200):**
```json
{
  "id": 123,
  "status": "checked_out",
  "actual_check_out": "2025-06-09T11:00:00Z",
  "nights_stayed": 3,
  "balance_due": 0.00,
  "room": {
    "id": 301,
    "status": "cleaning"
  }
}
```

**Error Responses:**
- `400` — Invalid reservation status (must be checked_in)
- `404` — Reservation not found
- `422` — Outstanding balance (if policy requires payment before checkout)

---

### 6. GET /api/checkin/{reservation_id}/status
**Purpose:** Lightweight endpoint to check current check-in status

**Response (200):**
```json
{
  "reservation_id": 123,
  "status": "checked_in",
  "guest_name": "Juan Pérez",
  "room_id": 301,
  "actual_check_in": "2025-06-09T14:30:00Z",
  "expected_check_out": "2025-06-12T11:00:00Z",
  "balance_due": 0.00,
  "room_status": "occupied"
}
```

---

## Block Execution Diagram

```
┌─────────────────────────────────────────────────────────┐
│ POST /api/checkin/{reservation_id}                       │
│                                                          │
│ Input: { reservation_id, signature, accept_terms }      │
└──────────────────────────┬────────────────────────────────┘
                           │
                    ┌──────▼───────┐
                    │ Block 1:     │ ✓ Pass → continue
                    │ Res. Status  │ ✗ Fail → 400
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Block 2:     │ ✓ Pass → continue
                    │ Guest Exist  │ ✗ Fail → 404
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Block 3:     │ ✓ Pass → continue
                    │ Guest Data   │ ✗ Fail → 422
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Block 4:     │ ✓ Pass → continue
                    │ Doc Format   │ ✗ Fail → 422
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Block 5:     │ ✓ Pass → continue
                    │ Room Avail.  │ ✗ Fail → 409
                    └──────┬───────┘
                           │
                    ┌──────▼───────┐
                    │ Block 6:     │ ✓ Pass → commit
                    │ Check-in Doc │ ✗ Fail → 500
                    └──────┬───────┘
                           │
        ┌──────────────────▼─────────────────┐
        │ Commit Transaction                  │
        │ • Update reservation.status         │
        │ • Update room.status                │
        │ • Record actual_check_in timestamp  │
        └──────────────────┬─────────────────┘
                           │
                    ┌──────▼───────┐
                    │ 200 OK       │
                    │ Full Response│
                    └──────────────┘
```

---

## Data Models & Relationships

### CheckinValidationResult (Internal)
```python
@dataclass
class CheckinValidationResult:
    reservation_id: int
    can_proceed: bool
    blocks: list[BlockCheckResult]
    first_blocking_error: BlockCheckError | None
    missing_fields: list[str]
    jurisdiction_code: str
```

### BlockCheckResult (Internal)
```python
@dataclass
class BlockCheckResult:
    block_id: str  # "reservation_status" | "guest_existence" | ...
    status: str   # "pass" | "fail" | "skip"
    message: str
    metadata: dict = None  # block-specific data
```

### BlockCheckError (Exception)
```python
class BlockCheckError(Exception):
    def __init__(
        self,
        code: str,  # "invalid_reservation_status" | "guest_not_found" | ...
        message: str,
        http_status: int = 400,
        metadata: dict = None
    ):
        self.code = code
        self.message = message
        self.http_status = http_status
        self.metadata = metadata or {}
```

---

## State Machine Transitions

```
PENDING ──[deposit_paid]──► DEPOSIT_PAID
                │
                └─[fully_paid]──► FULLY_PAID
                                  │
                                  ├─[check_in + all validations]──► CHECKED_IN
                                  │                                  │
                                  │                                  └─[checkout]──► CHECKED_OUT
                                  │
                                  └─[cancel]──► CANCELLED

FULLY_PAID ──[no_show]──► NO_SHOW
FULLY_PAID ──[cancel]──► CANCELLED
CHECKED_IN ──[cancel]──► CANCELLED (with refund handling)
```

---

## Error Handling Strategy

### Validation Errors (422)
Return all missing fields in one response to guide user.

```json
{
  "error": "validation_failed",
  "blocks": [
    {
      "block_id": "guest_data_completeness",
      "missing": ["Document type is required", "Terms acceptance required"]
    }
  ]
}
```

### State Errors (400, 409)
Cannot proceed due to reservation or room state.

```json
{
  "error": "invalid_state",
  "code": "invalid_reservation_status",
  "current_status": "pending",
  "expected_status": "fully_paid",
  "message": "Cannot check in: outstanding balance $250.00"
}
```

### System Errors (500)
Document generation or transaction failures.

```json
{
  "error": "system_error",
  "code": "document_generation_failed",
  "message": "Could not generate check-in PDF",
  "details": "Template not found for jurisdiction AR"
}
```

---

## Implementation Checklist

- [ ] **Models:** CheckinValidationResult, BlockCheckResult, BlockCheckError
- [ ] **Services:** CheckinValidator (blocks 1-6), CheckinService (orchestration)
- [ ] **Endpoints:** 6 endpoints (checkin, validate, validate-guest, document, checkout, status)
- [ ] **Document Generation:** Jinja2 templates for AR/UY/CL PDFs
- [ ] **Tests:** 
  - Unit tests per block
  - Integration tests for full flow
  - Edge cases (room unavailable, missing fields, etc.)
- [ ] **Frontend Integration:** Signature capture, field validation, progress UI
- [ ] **Audit Logging:** Record all check-in/checkout events with user & timestamp

---

## Security & Compliance

- **PII Handling:** Guest documents (DNI, passport) stored encrypted
- **Signature:** Base64-encoded PNG/SVG, timestamped, audit-trailed
- **Terms Acceptance:** Immutable record linked to check-in event
- **Jurisdiction Compliance:** AR regulations enforced (guest ledger forms, retention policy)
- **Room Isolation:** Check-in only if room_id exists & belongs to hotel
- **Idempotency:** Multiple check-in requests for same reservation should be safe (2nd call returns 400 "already checked in")

---

## Version History

| Date | Author | Change |
|------|--------|--------|
| 2026-06-09 | Claude | Initial design document |
