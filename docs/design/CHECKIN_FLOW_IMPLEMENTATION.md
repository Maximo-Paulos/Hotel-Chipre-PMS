# Check-in Flow Implementation Guide

## Overview

Complete check-in system for Hotel Chipre PMS with multi-step workflow:
1. **Prefinalized** - Review reservation and payment status
2. **Guest Aggregation** - Manage primary + additional guests with documents
3. **Validation** - Run all check-in validation blocks
4. **Room Change** - Optionally reassign room before finalization
5. **Confirmation** - Final review and execute check-in

---

## Components

### 1. CheckinFlow Component (`frontend/src/components/CheckinFlow.tsx`)

**Main check-in workflow modal** with 5-step guided process.

#### Props
```typescript
interface CheckinFlowProps {
  reservation: Reservation;        // Reservation to check in
  isOpen: boolean;                 // Modal visibility
  onClose: () => void;            // Close handler
  onSuccess?: (reservation: Reservation) => void;  // Success callback
}
```

#### Key Features
- **Step Progress** - Visual progress indicator
- **Guest Aggregation** - Add/remove additional guests with document validation
- **Validation Blocks** - Multi-level validation (critical + warning)
- **Balance Check** - Clear payment status with amount due
- **Do Not Disturb Block** - Prevent check-in for restricted guests
- **Room Change** - Change room assignment with availability check
- **Confirmation Review** - Final summary before committing

#### Sub-components
```typescript
GuestAggregationSection     // Manage guests + documents
ValidationSection           // Display validation blocks
BalanceCheckSection         // Show payment status
DoNotDisturbSection         // Block restricted guests
RoomChangeSection           // Select alternative room
ConfirmationSection         // Final review
```

---

### 2. CheckInPage Component (`frontend/src/views/protected/CheckInPage.tsx`)

**Main page** listing all reservations with check-in capability.

#### Features
- **Search & Filter** - By guest name, document number, confirmation code
- **Status Indicators** - Ready, Needs Validation, Blocked, Checked In
- **Statistics Cards** - Count by status
- **Reservation Cards** - Quick view with check-in action button
- **Status Colors**
  - Green (Emerald) = Ready
  - Amber = Needs Validation
  - Red (Rose) = Blocked
  - Blue = Checked In

#### Status Logic
```typescript
type CheckinStatus = "ready" | "needs_validation" | "blocked" | "checked_in";

// Automatic status determination
getCheckInStatus(reservation): [CheckinStatus, string]
  - "checked_in" if already checked in
  - "blocked" if requires_manual_review
  - "needs_validation" if not fully paid or guest data incomplete
  - "ready" if all checks pass
```

---

### 3. useCheckin Hook (`frontend/src/hooks/useCheckin.ts`)

**Comprehensive hook** for all check-in operations.

#### API Functions
```typescript
validateCheckin(reservationId, session)
  → CheckinValidationResponse
  
validateGuestData(reservationId, guestId, updates, session)
  → CheckinValidationResponse
  
performCheckin(reservationId, payload, session)
  → CheckinResult
  
changeRoom(reservationId, newRoomId, reason, session)
  → { success: boolean; room_id: number }
  
getCheckinStatus(reservationId, session)
  → { reservation_id, status, actual_check_in, checked_in_by }
```

#### Mutations
```typescript
useCheckinMutations() returns {
  validateGuestMutation    // Validate + update guest data
  performCheckinMutation   // Execute check-in
  changeRoomMutation       // Change room before finalization
}
```

#### Queries
```typescript
useCheckinValidation(reservationId)     // Pre-flight validation
useCheckinStatus(reservationId)         // Monitor check-in status
```

---

## Validation Blocks

### Block Types
```typescript
interface ValidationBlock {
  id: string;                    // Unique ID
  label: string;                 // User-friendly label
  status: "pass" | "fail" | "pending";
  message: string;               // Status message
  details?: Record<string, any>; // Extra details
}
```

### Built-in Blocks

| Block ID | Label | Severity | Check |
|----------|-------|----------|-------|
| `reservation_status` | Estado de reserva | critical | Must be fully_paid or deposit_paid |
| `guest_complete` | Datos del huésped | critical | Document type + number required |
| `balance_check` | Saldo adeudado | critical | Balance due <= 0 |
| `do_not_disturb` | Verificación prohibido alojar | critical | Guest not blacklisted |
| `room_assigned` | Habitación asignada | warning | Room ID exists |

### Severity Levels
- **critical** - Blocks check-in if failed
- **warning** - Non-blocking but should be reviewed

---

## Guest Aggregation

### GuestEntry Structure
```typescript
interface GuestEntry {
  id: number;
  firstName: string;
  lastName: string;
  documentType: string;        // DNI, PASSPORT, CEDULA
  documentNumber: string;
  isPrimary: boolean;          // Cannot remove primary guest
}
```

### Features
- **Primary Guest** - Cannot be removed
- **Additional Guests** - Can add/remove dynamically
- **Document Types** - Select from predefined list
- **Validation** - All guests require full document info

---

## Balance Check System

### Balance Calculation
```typescript
balanceDue = reservation.balance_due 
  || (reservation.total_amount - reservation.amount_paid)

isPaid = balanceDue <= 0
```

### Display Logic
- Shows Total, Paid, and Due amounts
- Color-coded:
  - Emerald = Paid in full
  - Rose = Outstanding balance
- Warning badge if balance due

---

## Do Not Disturb Block

### Behavior
```typescript
// Checkbox in Room Change step
- Checked = Guest blocked, cannot check in
- Prevents progression to Confirmation step
- Shows red warning if checked
```

### Future Enhancement
- Query actual `do_not_disturb` flag from database
- Show blacklist reason in details
- Audit log when blocked

---

## Room Change System

### RoomChangeOption Structure
```typescript
interface RoomChangeOption {
  roomId: number;
  roomNumber: string;
  categoryId: number;
  categoryName: string;
  available: boolean;
  reason?: string;              // e.g., "No disponible en fechas"
}
```

### Flow
1. Display current room (if assigned)
2. Load available alternatives
3. Allow radio selection
4. Update on selection (mutation)
5. Show confirmation summary

### When Available
- Before Confirmation step only
- Can be changed without committing
- Optional - can skip this step

---

## Step Navigation

### Step Order
```
prefinal → guests → validation → room_change → confirmation
```

### Progression Rules
| Step | Can Proceed If |
|------|----------------|
| prefinal | Always |
| guests | Has at least 1 guest |
| validation | No critical failures |
| room_change | Not blocked |
| confirmation | Always → Proceed to check-in |

---

## Error Handling

### Blocking Issues
```typescript
// Displayed if critical validations fail
blockingIssues: [
  {
    block_id: string;
    field?: string;
    message: string;  // User-friendly error
  }
]
```

### User Feedback
- **Critical Errors** - Red banner, prevents progression
- **Warnings** - Amber badge, non-blocking
- **Success** - Green checkmark
- **Loading** - Spinning icon

---

## Integration Points

### API Endpoints (Required)

#### 1. Validate Check-in
```
GET /api/checkin/validate/{reservation_id}
→ CheckinValidationResponse
```

#### 2. Validate Guest Data
```
POST /api/checkin/{reservation_id}/validate-guest
Body: { guest_id, updates }
→ CheckinValidationResponse
```

#### 3. Perform Check-in
```
POST /api/checkin/{reservation_id}
Body: {
  digital_signature?: string,
  signature_timestamp?: string,
  accept_terms: boolean,
  special_requests?: string
}
→ CheckinResult
```

#### 4. Change Room
```
PATCH /api/reservations/{reservation_id}/room
Body: { room_id: number, change_reason?: string }
→ { success: boolean, room_id: number }
```

#### 5. Check-in Status
```
GET /api/checkin/{reservation_id}/status
→ {
  reservation_id: number,
  status: string,
  actual_check_in?: string,
  checked_in_by?: string
}
```

### Query Invalidation
After successful check-in, these caches are cleared:
```typescript
["reservation", hotelId, reservationId]
["reservations", hotelId]
["checkin-validation", hotelId, reservationId]
["payment-summary", hotelId, reservationId]
```

---

## Usage Example

### In CheckInPage
```tsx
const [selectedReservation, setSelectedReservation] = useState(null);

return (
  <>
    <ReservationCard
      reservation={reservation}
      onCheckinClick={setSelectedReservation}
    />
    
    <CheckinFlow
      reservation={selectedReservation}
      isOpen={!!selectedReservation}
      onClose={() => setSelectedReservation(null)}
      onSuccess={(updatedRes) => {
        // Refresh or update local state
      }}
    />
  </>
);
```

---

## Styling & Colors

### Tailwind Palette
```
Primary (Actions): blue-600, blue-700
Success: emerald-600, emerald-700
Warning: amber-100, amber-700
Error: rose-100, rose-700
Neutral: slate-* (50-900)
```

### Component Sizes
- Modal: max-w-2xl (672px)
- Cards: p-4 (16px padding)
- Text: text-sm (14px), text-xs (12px)
- Icons: w-4 h-4 (16px), w-5 h-5 (20px)

---

## Future Enhancements

### Phase 2
- [ ] Digital signature capture
- [ ] PDF generation for check-in receipt
- [ ] SMS/Email confirmation
- [ ] Guest consent forms
- [ ] Photo ID verification

### Phase 3
- [ ] Biometric check-in
- [ ] QR code scanning
- [ ] Multi-property check-in
- [ ] Batch check-in operations
- [ ] Analytics & reporting

---

## Testing Checklist

### Unit Tests
- [ ] Guest add/remove logic
- [ ] Status determination (ready/blocked/etc)
- [ ] Balance calculation
- [ ] Validation block rendering

### Integration Tests
- [ ] Full check-in flow (all 5 steps)
- [ ] Room change with mutation
- [ ] Validation error handling
- [ ] Query invalidation after check-in

### E2E Tests
- [ ] Search & filter reservations
- [ ] Open/close check-in modal
- [ ] Progress through all steps
- [ ] Cancel and restart
- [ ] Verify final state

---

## File Locations

```
frontend/src/
├── components/
│   └── CheckinFlow.tsx              [Main workflow component]
├── hooks/
│   └── useCheckin.ts                [Check-in operations hook]
├── views/protected/
│   └── CheckInPage.tsx              [Main listing page]
└── api/
    └── [reservations.ts - existing]
```

---

## Notes

- All timestamps are ISO 8601 format
- Guest documents support: DNI, Passport, Cédula
- Mock data for room availability in current implementation
- Balance calculations use `reservation.balance_due` or compute from totals
- Do Not Disturb flag can be extended to query actual database status
