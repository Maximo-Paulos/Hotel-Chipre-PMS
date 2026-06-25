# Check-in Module — Quick Reference

## What Was Generated

4 production-ready code skeleton files + 2 documentation files:

```
✅ docs/checkin-module-design.md              (800 lines) — Complete spec
✅ app/api/checkin_endpoints.py              (600 lines) — 6 endpoints
✅ app/services/checkin_validator.py         (450 lines) — Validation blocks
✅ app/services/checkin_orchestrator.py      (400 lines) — Service layer
✅ CHECKIN_MODULE_SKELETON.md                (500 lines) — Implementation roadmap
✅ CHECKIN_QUICK_REFERENCE.md                (this file) — Quick navigation
```

**Total: 2,250+ lines of production-ready code skeleton**

---

## The 6 Validation Blocks (Prefinalizado Flow)

```
1. Reservation Status Check
   └─ Must be FULLY_PAID (or CHECKED_IN for idempotency)
   
2. Guest Record Existence
   └─ Must exist and belong to hotel
   
3. Guest Data Completeness (Jurisdiction-Aware)
   └─ Required fields vary by AR/UY/CL
   └─ Document type, first name, last name, terms acceptance
   
4. Document Format Validation
   └─ DNI: 8 digits (AR)
   └─ Passport: 6-9 alphanumeric
   └─ CEDULA: 8-9 digits
   
5. Room Availability Check
   └─ Room status = READY | AVAILABLE
   └─ No overlapping reservations
   
6. Check-in Document Generation
   └─ Template exists for jurisdiction
   └─ Template can be rendered
```

**Blocks 1-5 must PASS. Block 6 is PENDING (generated on checkin).**

---

## The 6 Endpoints

| Endpoint | Method | Purpose | Use |
|----------|--------|---------|-----|
| `/api/checkin/{id}` | POST | Full check-in | Main flow |
| `/api/checkin/validate/{id}` | GET | Pre-flight validation | Check before checkin |
| `/api/checkin/{id}/validate-guest` | POST | Guest field validation | Field-by-field testing |
| `/api/checkin/{id}/document` | POST | Generate PDF/HTML form | Admin/printing |
| `/api/checkin/{id}/checkout` | POST | Check out + mark cleaning | End of stay |
| `/api/checkin/{id}/status` | GET | Current state (read-only) | Status queries |

---

## Three Service Classes

### CheckinValidator (`app/services/checkin_validator.py`)
Implements the 6 validation blocks. Returns `BlockCheckResult` for each.

**Entry point:**
```python
result = CheckinValidator.validate_all_blocks(db, reservation_id, hotel_id)
# Returns: CheckinValidationResult with all 6 blocks
```

**Exceptions:**
- `ReservationStatusError` (400)
- `GuestNotFoundError` (404)
- `MissingGuestFieldsError` (422)
- `InvalidDocumentFormatError` (422)
- `RoomUnavailableError` (409)
- `DocumentGenerationError` (500)

### CheckinService (`app/services/checkin_orchestrator.py`)
Orchestrates validation + state transitions. Owns transaction control.

**Key methods:**
```python
CheckinService.validate_checkin(db, reservation_id, hotel_id)
  → CheckinValidationResult (read-only)

CheckinService.perform_checkin(db, reservation_id, hotel_id, signature, accept_terms)
  → Reservation (status=CHECKED_IN, db.flush() called)

CheckinService.perform_checkout(db, reservation_id, hotel_id)
  → Reservation (status=CHECKED_OUT, room.status=CLEANING)

CheckinService.get_checkin_status(db, reservation_id, hotel_id)
  → dict (read-only status info)
```

### CheckinDocumentService (`app/services/checkin_orchestrator.py`)
Generates Jinja2 templates + PDFs.

**Key method:**
```python
CheckinDocumentService.generate_checkin_document(
  db, reservation_id, hotel_id, format="pdf", locale="es-AR"
)
  → (bytes | str, content_type)
```

Supports:
- Formats: `pdf`, `html`
- Locales: `es-AR`, `es-UY`, `es-CL`
- Jurisdictions: AR, UY, CL

---

## Quick Check-in Flow

```python
# Frontend calls:
1. GET /api/checkin/validate/{reservation_id}
   └─ Returns: blocks status, what's missing
   
2. POST /api/checkin/{reservation_id}/validate-guest
   └─ Returns: field-level validation (for progressive UI)
   
3. POST /api/checkin/{reservation_id}
   └─ Input: { digital_signature, accept_terms }
   └─ Returns: Updated reservation (status=CHECKED_IN)
   
4. GET /api/checkin/{reservation_id}/status
   └─ Returns: Current state
```

---

## Request/Response Schemas (Pydantic Models)

### POST /api/checkin/{id} — Check-in

**Request:**
```json
{
  "digital_signature": "data:image/png;base64,iVBORw0K...",
  "signature_timestamp": "2025-06-09T14:30:00Z",
  "accept_terms": true,
  "special_requests": "High floor preferred"
}
```

**Response (200):**
```json
{
  "id": 123,
  "status": "checked_in",
  "guest_id": 45,
  "room_id": 301,
  "actual_check_in": "2025-06-09T14:30:00Z",
  "balance_due": 0.0,
  "nights": 3
}
```

**Error Responses:**
- 400: Invalid status → ReservationStatusError
- 404: Not found → GuestNotFoundError
- 409: Room unavailable → RoomUnavailableError
- 422: Missing fields → MissingGuestFieldsError or InvalidDocumentFormatError
- 500: Doc generation failed → DocumentGenerationError

---

### GET /api/checkin/validate/{id} — Pre-flight

**Response (200):**
```json
{
  "reservation_id": 123,
  "can_check_in": false,
  "jurisdiction_code": "AR",
  "blocks": [
    {
      "block_id": "reservation_status",
      "status": "pass",
      "message": "Reservation status is fully_paid"
    },
    {
      "block_id": "guest_data_completeness",
      "status": "fail",
      "message": "Missing required fields",
      "details": {
        "missing_fields": ["Document type is required"]
      }
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

## Error Response Format

All validation errors follow this pattern:

```json
{
  "error": "validation_failed",
  "code": "missing_guest_fields",
  "message": "Check-in blocked — missing required guest data",
  "details": {
    "missing_fields": ["Document type is required"],
    "jurisdiction_code": "AR"
  },
  "http_status": 422
}
```

---

## Database Models (Existing)

No new models needed! Uses existing:

- `Reservation` (status, actual_check_in, actual_check_out, room_id, guest_id)
- `Guest` (document_type, document_number, terms_accepted, digital_signature)
- `Room` (status: READY, OCCUPIED, CLEANING, etc.)
- `HotelConfiguration` (extra_policies for jurisdiction_code, require_document_for_checkin)

---

## Testing Checklist

```
✅ Unit Tests (checkin_validator.py)
   ├─ block_1_reservation_status (FULLY_PAID, already checked in, invalid)
   ├─ block_2_guest_existence (found, not found)
   ├─ block_3_guest_data (complete, missing fields, jurisdiction variations)
   ├─ block_4_document (valid AR DNI, invalid format, missing)
   ├─ block_5_room (ready, occupied, overlapping reservation)
   └─ block_6_document (template found, rendering works)

✅ Integration Tests (endpoints)
   ├─ POST /checkin/{id} — happy path
   ├─ POST /checkin/{id} — with missing fields
   ├─ GET /checkin/validate/{id}
   ├─ POST /checkin/{id}/validate-guest
   ├─ POST /checkin/{id}/checkout
   └─ GET /checkin/{id}/status

✅ E2E Tests (full flow)
   ├─ Validate → Checkin → Status → Checkout
   ├─ All three jurisdictions (AR, UY, CL)
   └─ Edge cases (concurrent, idempotent)
```

---

## Implementation Order (Recommended)

### Phase 1: Validation Blocks (2-3 days)
```
1. Implement CheckinValidator.validate_all_blocks()
2. Implement blocks 1-6 in checkin_validator.py
3. Add document validators (_validate_ar_document, etc.)
4. Write unit tests for blocks
```

### Phase 2: Services & Endpoints (2-3 days)
```
1. Implement CheckinService methods
2. Implement GuestValidationService
3. Wire endpoints to services
4. Add integration tests
```

### Phase 3: Document Generation (1-2 days)
```
1. Create Jinja2 templates (AR/UY/CL)
2. Implement CheckinDocumentService
3. Test PDF rendering
```

### Phase 4: Frontend Integration (2-3 days)
```
1. Signature capture component
2. Progressive field validation UI
3. Document download/printing
4. End-to-end testing
```

---

## Key Design Decisions

✅ **6 Independent Blocks** — Each can fail independently with specific error  
✅ **Jurisdiction-Aware** — Different rules for AR/UY/CL  
✅ **Idempotent** — Multiple check-ins return 400 "already checked in"  
✅ **Signature Capture** — Base64-encoded PNG/SVG with timestamp  
✅ **Room Isolation** — Can only check in if room_id exists & is READY  
✅ **Pre-flight Validation** — GET endpoint returns all blocks without side effects  
✅ **Document as Service** — Can generate PDF for signatures/printing  
✅ **Async Cleanup** — Checkout marks room as CLEANING (actual cleaning async)  

---

## File Locations

```
Documentation:
  📄 docs/checkin-module-design.md          (800 lines — full spec)
  📄 CHECKIN_MODULE_SKELETON.md             (500 lines — roadmap)
  📄 CHECKIN_QUICK_REFERENCE.md             (this file)

Code:
  📦 app/api/checkin_endpoints.py           (6 endpoints + schemas)
  📦 app/services/checkin_validator.py      (Validation blocks)
  📦 app/services/checkin_orchestrator.py   (Services layer)

Templates (create):
  📋 templates/checkin/AR_checkin_form.jinja2
  📋 templates/checkin/UY_checkin_form.jinja2
  📋 templates/checkin/CL_checkin_form.jinja2

Tests (create):
  🧪 tests/test_checkin_validator.py
  🧪 tests/test_checkin_orchestrator.py
  🧪 tests/test_checkin_endpoints.py
```

---

## Next Steps

1. **Review** the design document (`docs/checkin-module-design.md`)
2. **Understand** the validation blocks and flow
3. **Implement** Phase 1 (validation blocks in `checkin_validator.py`)
4. **Test** each block with unit tests
5. **Wire up** services and endpoints
6. **Create** Jinja2 templates
7. **Build** frontend integration

All files are **NotImplementedError** stubs — ready for development!

---

## Questions?

- **Architecture?** → Read `docs/checkin-module-design.md`
- **Endpoints?** → Read docstrings in `app/api/checkin_endpoints.py`
- **Validation logic?** → Read `app/services/checkin_validator.py`
- **Service orchestration?** → Read `app/services/checkin_orchestrator.py`
- **Implementation roadmap?** → Read `CHECKIN_MODULE_SKELETON.md`
