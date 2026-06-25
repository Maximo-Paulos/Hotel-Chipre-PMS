# Check-in Module — Code Skeleton Summary

## Overview
Complete skeleton for the Hotel Chipre Check-in module with:
- **Prefinalizado flow** (6 validation blocks)
- **Endpoint specifications** (6 endpoints)
- **Domain models & exceptions**
- **Service layer architecture**

All files are in place with `NotImplementedError` stubs ready for development.

---

## Generated Files

### 1. Design Document
**File:** `docs/checkin-module-design.md`

Complete specification including:
- Flow diagram (state machine transitions)
- 6 validation blocks (purpose, conditions, errors)
- 6 endpoint specifications with request/response schemas
- Block execution diagram
- Error handling strategy
- Data models (CheckinValidationResult, BlockCheckResult, etc.)
- Security & compliance considerations

### 2. Endpoint Skeleton
**File:** `app/api/checkin_endpoints.py` (600+ lines)

**6 Endpoints:**

```
1. POST /api/checkin/{reservation_id}
   ├─ Full check-in with all validations
   ├─ Request: CheckinRequest (signature, accept_terms, special_requests)
   └─ Response: ReservationRead

2. GET /api/checkin/validate/{reservation_id}
   ├─ Pre-flight validation (no state changes)
   ├─ Response: CheckinValidationResponse (blocks, issues, can_check_in)
   └─ Use: Check what will pass/fail before actual check-in

3. POST /api/checkin/{reservation_id}/validate-guest
   ├─ Validate guest fields before check-in
   ├─ Request: ValidateGuestRequest (guest_id, updates)
   └─ Response: ValidateGuestResponse (validation_blocks, missing_fields)

4. POST /api/checkin/{reservation_id}/document
   ├─ Generate jurisdiction-specific check-in PDF/HTML
   ├─ Query params: format (pdf|html), locale (es-AR|es-UY|es-CL)
   └─ Response: PDF binary or HTML with document

5. POST /api/checkin/{reservation_id}/checkout
   ├─ Check out reservation and mark room for cleaning
   ├─ Request: CheckoutRequest (checkout_notes, refund_note)
   └─ Response: CheckoutResponse (status, room_status, nights_stayed)

6. GET /api/checkin/{reservation_id}/status
   ├─ Lightweight status query
   ├─ Response: CheckinStatusResponse (current state)
   └─ Use: Non-validating read for dashboard
```

**Includes:**
- Comprehensive Pydantic schemas (request/response)
- Detailed docstrings
- Error codes and HTTP status mappings
- JSON schema examples for Swagger UI

### 3. Validation Blocks Skeleton
**File:** `app/services/checkin_validator.py` (450+ lines)

**CheckinValidator class with 6 blocks:**

```
Block 1: Reservation Status Verification
├─ Verify FULLY_PAID status
├─ Handle idempotent re-entry (CHECKED_IN)
└─ Error: ReservationStatusError

Block 2: Guest Record Existence & Scope
├─ Load guest with hotel_id scope
├─ Verify not soft-deleted
└─ Error: GuestNotFoundError

Block 3: Guest Data Completeness
├─ Jurisdiction-aware field validation
├─ Uses compute_missing_guest_fields()
└─ Error: MissingGuestFieldsError

Block 4: Document Format Validation
├─ AR: DNI (8 digits), Passport (6-9 alphanum), CEDULA
├─ UY: Similar with nationality check
├─ CL: Similar with country/nationality check
└─ Error: InvalidDocumentFormatError

Block 5: Room Availability Check
├─ Room exists & belongs to hotel
├─ Status is READY or AVAILABLE
├─ No overlapping reservations
└─ Error: RoomUnavailableError

Block 6: Check-in Document Generation
├─ Verify Jinja2 template exists
├─ Test template rendering
└─ Error: DocumentGenerationError
```

**Includes:**
- Context object (CheckinValidationContext)
- Result objects (BlockCheckResult, CheckinValidationResult)
- Custom exception hierarchy
- Utility methods for loading context & jurisdiction profiles

### 4. Orchestrator Service Skeleton
**File:** `app/services/checkin_orchestrator.py` (400+ lines)

**Three main services:**

#### CheckinService
```python
.validate_checkin(db, reservation_id, hotel_id)
  ├─ Run all validation blocks (read-only)
  └─ Return CheckinValidationResult

.perform_checkin(db, reservation_id, hotel_id, signature, accept_terms, special_requests)
  ├─ Run all validation blocks
  ├─ Verify FULLY_PAID
  ├─ Record digital signature
  ├─ Update guest.terms_accepted
  ├─ Transition to CHECKED_IN
  ├─ Record actual_check_in timestamp
  ├─ Update room.status = OCCUPIED
  └─ Return Reservation

.perform_checkout(db, reservation_id, hotel_id, checkout_notes, refund_note)
  ├─ Verify CHECKED_IN status
  ├─ Check outstanding balance
  ├─ Transition to CHECKED_OUT
  ├─ Record actual_check_out timestamp
  ├─ Update room.status = CLEANING
  └─ Return Reservation

.get_checkin_status(db, reservation_id, hotel_id)
  └─ Return current state (read-only)
```

#### CheckinDocumentService
```python
.generate_checkin_document(db, reservation_id, hotel_id, format, locale)
  ├─ Load reservation + guest + room
  ├─ Get jurisdiction profile
  ├─ Load Jinja2 template (AR/UY/CL)
  ├─ Render template
  ├─ Convert to PDF if requested
  └─ Return (content, content_type)

._get_template_path(jurisdiction_code)
._render_html(template_path, context)
._render_pdf(html_string)
```

#### GuestValidationService
```python
.validate_guest_fields(db, guest_id, hotel_id, updates)
  ├─ Load guest
  ├─ Apply temporary updates (not persisted)
  ├─ Validate each field
  ├─ Check document format
  └─ Return validation_blocks list

._validate_document_field(document_type, document_number, jurisdiction_code)
```

---

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────┐
│ API LAYER (checkin_endpoints.py)                            │
│ • 6 endpoints with Pydantic schemas                         │
│ • Request/response validation                               │
│ • HTTP status code mapping                                  │
│ • Auth context dependency (hotel_id scoping)                │
└────────────┬─────────────────────────────────────────────────┘
             │
┌────────────▼──────────────────────────────────────────────────┐
│ SERVICE LAYER (checkin_orchestrator.py)                      │
│                                                               │
│ CheckinService (orchestration)                               │
│ ├─ validate_checkin()                                        │
│ ├─ perform_checkin()                                         │
│ ├─ perform_checkout()                                        │
│ └─ get_checkin_status()                                      │
│                                                               │
│ CheckinDocumentService (document generation)                 │
│ ├─ generate_checkin_document()                               │
│ └─ _render_html() / _render_pdf()                            │
│                                                               │
│ GuestValidationService (guest field validation)              │
│ └─ validate_guest_fields()                                   │
└────────────┬──────────────────────────────────────────────────┘
             │
┌────────────▼──────────────────────────────────────────────────┐
│ VALIDATION LAYER (checkin_validator.py)                      │
│                                                               │
│ CheckinValidator (block orchestration)                       │
│ ├─ validate_all_blocks() [main entry]                        │
│ ├─ block_1_reservation_status()                              │
│ ├─ block_2_guest_existence()                                 │
│ ├─ block_3_guest_data_completeness()                         │
│ ├─ block_4_document_validation()                             │
│ │   ├─ _validate_ar_document()                               │
│ │   ├─ _validate_uy_document()                               │
│ │   └─ _validate_cl_document()                               │
│ ├─ block_5_room_availability()                               │
│ └─ block_6_checkin_document()                                │
│                                                               │
│ Exception Hierarchy:                                         │
│ ├─ CheckinValidationError (base)                             │
│ ├─ ReservationStatusError                                    │
│ ├─ GuestNotFoundError                                        │
│ ├─ MissingGuestFieldsError                                   │
│ ├─ InvalidDocumentFormatError                                │
│ ├─ RoomUnavailableError                                      │
│ └─ DocumentGenerationError                                   │
└────────────┬──────────────────────────────────────────────────┘
             │
┌────────────▼──────────────────────────────────────────────────┐
│ DEPENDENT SERVICES (existing)                                │
│                                                               │
│ • reservation_service.transition_reservation_status()        │
│ • jurisdiction_profile.get_profile()                         │
│ • jurisdiction_profile.compute_missing_guest_fields()        │
│ • guest_profile.validate_primary_guest_record()              │
│ • Database models: Reservation, Guest, Room, etc.            │
└──────────────────────────────────────────────────────────────┘
```

---

## Implementation Roadmap

### Phase 1: Core Validation (Priority 1)
- [ ] Implement CheckinValidator.validate_all_blocks()
- [ ] Implement blocks 1-2 (reservation status, guest existence)
- [ ] Implement blocks 3-4 (guest data, document format)
- [ ] Add document format validators (_validate_ar_document, etc.)
- [ ] Test with unit tests

### Phase 2: Endpoints & Orchestration (Priority 2)
- [ ] Implement CheckinService.validate_checkin()
- [ ] Implement CheckinService.perform_checkin()
- [ ] Implement CheckinService.perform_checkout()
- [ ] Implement CheckinService.get_checkin_status()
- [ ] Wire up endpoints to services
- [ ] Add integration tests

### Phase 3: Document Generation (Priority 3)
- [ ] Create Jinja2 templates (AR_checkin_form.jinja2, etc.)
- [ ] Implement CheckinDocumentService.generate_checkin_document()
- [ ] Add WeasyPrint/wkhtmltopdf integration
- [ ] Test PDF generation with sample data

### Phase 4: Guest Validation & Frontend Integration (Priority 4)
- [ ] Implement GuestValidationService.validate_guest_fields()
- [ ] Wire up /validate-guest endpoint
- [ ] Frontend: Signature capture component
- [ ] Frontend: Field validation hooks
- [ ] End-to-end testing

### Phase 5: Edge Cases & Refinement (Priority 5)
- [ ] Idempotency handling (re-checkin same reservation)
- [ ] Concurrent checkout handling
- [ ] Refund workflow for early checkout
- [ ] Audit logging for all transitions
- [ ] Performance testing with large guest datasets

---

## Testing Strategy

### Unit Tests
```
tests/test_checkin_validator.py
├─ test_block_1_reservation_status
├─ test_block_2_guest_existence
├─ test_block_3_guest_data_completeness
├─ test_block_4_document_validation
│  ├─ test_validate_ar_document
│  ├─ test_validate_uy_document
│  └─ test_validate_cl_document
├─ test_block_5_room_availability
└─ test_block_6_checkin_document

tests/test_checkin_orchestrator.py
├─ test_validate_checkin_all_pass
├─ test_validate_checkin_missing_fields
├─ test_perform_checkin_success
├─ test_perform_checkin_already_checked_in
├─ test_perform_checkout_success
└─ test_get_checkin_status
```

### Integration Tests
```
tests/test_checkin_endpoints.py
├─ test_endpoint_checkin_success
├─ test_endpoint_checkin_invalid_status
├─ test_endpoint_checkin_missing_guest_fields
├─ test_endpoint_validate_checkin
├─ test_endpoint_validate_guest
├─ test_endpoint_document_ar_pdf
├─ test_endpoint_document_uy_html
├─ test_endpoint_checkout_success
└─ test_endpoint_status
```

### E2E Tests
```
tests/smoke/test_checkin_flow.py
├─ Complete check-in flow: validate → signature → checkin
├─ Complete checkout flow
├─ Multiple languages (es-AR, es-UY, es-CL)
└─ Edge cases (concurrent access, rapid requests)
```

---

## Key Dependencies

### External Libraries
```python
# Already in project
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from pydantic import BaseModel

# Needed for document generation
from jinja2 import Environment, FileSystemLoader
from weasyprint import HTML, CSS  # or subprocess + wkhtmltopdf
import base64  # For signature handling

# Optional: signature validation
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.asymmetric import padding
```

### Existing Services
```python
from app.services.reservation_service import transition_reservation_status
from app.services.jurisdiction_profile import get_profile, compute_missing_guest_fields
from app.services.guest_profile import get_guest_profile
from app.models.reservation import Reservation, ReservationStatusEnum
from app.models.guest import Guest, DocumentTypeEnum
from app.models.room import Room, RoomStatusEnum
from app.models.hotel_config import HotelConfiguration
```

---

## Configuration & Templates

### Environment Variables
```bash
# Document generation
CHECKIN_DOCUMENT_FORMAT=pdf  # pdf or html
CHECKIN_TEMPLATE_DIR=templates/checkin

# Security
SIGNATURE_VALIDATION_ENABLED=true
SIGNATURE_KEY_PATH=/etc/pms/signature.key

# Jurisdiction defaults
DEFAULT_JURISDICTION_CODE=AR
REQUIRE_DOCUMENT_FOR_CHECKIN=true
REQUIRE_TERMS_ACCEPTANCE=true
```

### Template Structure
```
templates/checkin/
├─ AR_checkin_form.jinja2      # Argentina form
├─ UY_checkin_form.jinja2      # Uruguay form (experimental)
├─ CL_checkin_form.jinja2      # Chile form (experimental)
├─ _base_checkin_form.jinja2   # Base template (shared)
└─ _styles.css                 # Shared styles
```

### Template Variables
```python
{
    "hotel": HotelConfiguration,
    "reservation": Reservation,
    "guest": Guest,
    "room": Room,
    "generated_at": datetime,
    "jurisdiction_code": "AR",
    "locale": "es-AR",
    "room_policies": {...},
    "payment_summary": {...},
}
```

---

## Status & Next Steps

**Status:** Code skeleton 100% complete with design document.

**Ready for:**
1. ✅ Code review (design, architecture, schemas)
2. ✅ Frontend team integration (endpoint specs, response schemas)
3. ✅ Database team (models already exist)

**Next Steps:**
1. Implement Phase 1 (validation blocks)
2. Wire up Phase 2 (endpoints & orchestration)
3. Create Jinja2 templates (Phase 3)
4. Build frontend integration (Phase 4)

---

## Files Generated

| File | Lines | Purpose |
|------|-------|---------|
| `docs/checkin-module-design.md` | 800+ | Complete specification |
| `app/api/checkin_endpoints.py` | 600+ | API endpoints + schemas |
| `app/services/checkin_validator.py` | 450+ | Validation blocks |
| `app/services/checkin_orchestrator.py` | 400+ | Service orchestration |
| **TOTAL** | **2,250+** | Production-ready skeleton |

All files are in your git worktree ready for implementation.
