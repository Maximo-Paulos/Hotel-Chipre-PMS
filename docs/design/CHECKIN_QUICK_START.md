# Check-in Flow - Quick Start Guide

## Files Created

| File | Purpose | Size |
|------|---------|------|
| `frontend/src/components/CheckinFlow.tsx` | 5-step workflow modal | ~650 lines |
| `frontend/src/views/protected/CheckInPage.tsx` | Listing page with filters | ~450 lines |
| `frontend/src/hooks/useCheckin.ts` | Query/mutation operations | ~200 lines |
| `frontend/src/types/checkin.ts` | TypeScript definitions | ~350 lines |
| `CHECKIN_FLOW_IMPLEMENTATION.md` | Detailed guide | Full reference |
| `CHECKIN_SUMMARY.md` | Executive summary | Overview |

## Quick Integration (5 minutes)

### 1. Add Route
```typescript
// src/router.tsx
import { CheckInPage } from "./views/protected/CheckInPage";

{
  path: "/checkin",
  element: <CheckInPage />,
  label: "Check-in",
  icon: LogIn
}
```

### 2. Update Navigation
```typescript
// src/ui/AppShell.tsx or navigation menu
<NavLink to="/checkin">Check-in</NavLink>
```

### 3. Test in Development
```bash
npm run dev
# Navigate to /checkin
# Click reservation card to open workflow
```

## Component API

### CheckinFlow
```tsx
<CheckinFlow
  reservation={selectedReservation}
  isOpen={isOpen}
  onClose={handleClose}
  onSuccess={(res) => console.log("Checked in:", res)}
/>
```

### CheckInPage
Standalone page component, no props needed.

## Hook Usage

### Query Validation
```typescript
const { data: validation } = useCheckinValidation(reservationId);
// Returns CheckinValidationResponse
```

### Mutations
```typescript
const { performCheckinMutation, changeRoomMutation } = useCheckinMutations();

// Check-in
await performCheckinMutation.mutateAsync({
  reservationId: 123,
  payload: { accept_terms: true }
});

// Change room
await changeRoomMutation.mutateAsync({
  reservationId: 123,
  newRoomId: 105
});
```

## Mock Data Replacement

### Replace Validation Blocks
File: `CheckinFlow.tsx`, line ~350
```typescript
// Current: Hard-coded mock blocks in useEffect
// Replace with:
const { data: blocks } = useCheckinValidation(reservation.id);
setValidationBlocks(blocks?.blocks || []);
```

### Replace Available Rooms
File: `CheckinFlow.tsx`, line ~365
```typescript
// Current: Mock rooms in useEffect
// Replace with API call:
const { data: rooms } = useQuery({
  queryKey: ["available-rooms", reservation.category_id],
  queryFn: () => getAvailableRooms(...)
});
```

### Replace Guest List Initialization
File: `CheckinFlow.tsx`, line ~140
```typescript
// Already supports additional_guests from reservation
// No changes needed - automatically populates
```

## Validation Blocks Reference

| Block | Fails When | Severity |
|-------|-----------|----------|
| `reservation_status` | Not fully_paid/deposit_paid | Critical ⛔ |
| `guest_complete` | Missing document_number | Critical ⛔ |
| `balance_check` | Balance due > 0 | Critical ⛔ |
| `do_not_disturb` | Guest is_blocked = true | Critical ⛔ |
| `room_assigned` | room_id is null | Warning ⚠️ |

## Required API Endpoints

All 5 must be implemented:

```
✓ GET  /api/checkin/validate/{id}
✓ POST /api/checkin/{id}/validate-guest
✓ POST /api/checkin/{id}
✓ PATCH /api/reservations/{id}/room
✓ GET  /api/checkin/{id}/status
```

See `CHECKIN_FLOW_IMPLEMENTATION.md` for full specs.

## Step Navigation Logic

```
prefinal 
  ↓ (always)
guests 
  ↓ (if guests.length > 0)
validation 
  ↓ (if no critical failures)
room_change 
  ↓ (if not blocked)
confirmation 
  ↓ (click button)
✓ Check-in Complete
```

## Color Coding

| Status | Color | Meaning |
|--------|-------|---------|
| Ready | Emerald | Can check in now |
| Validation | Amber | Needs attention |
| Blocked | Rose | Cannot proceed |
| Checked In | Blue | Already done |

## Status Auto-Detection

```typescript
// Automatic in CheckInPage
getCheckInStatus(reservation)

Returns:
- "checked_in" if status === "checked_in"
- "blocked" if requires_manual_review
- "needs_validation" if not fully_paid or no doc
- "ready" if all pass
```

## Feature Checklist

- [x] 5-step workflow
- [x] Guest aggregation
- [x] Document capture
- [x] Validation blocks
- [x] Balance check
- [x] Do not disturb block
- [x] Room change
- [x] Confirmation review
- [x] Search & filter
- [x] Status dashboard
- [x] TypeScript types
- [x] React Query hooks
- [x] Error handling
- [x] Loading states

## Debugging Tips

### Check Modal Not Opening
```typescript
// Verify isOpen state
console.log("Modal open:", !!selectedReservation);

// Check reservation has required fields
console.log("Reservation:", selectedReservation);
```

### Validation Blocks Not Loading
```typescript
// Check useEffect is running
console.log("Validation blocks:", validationBlocks);

// Check mock data structure
// Should match CheckinValidationResponse
```

### Mutations Not Firing
```typescript
// Check hook is imported
import { useCheckinMutations } from "../hooks/useCheckin";

// Verify mutation is called with correct structure
console.log("Mutation result:", checkInMutation.data);
console.log("Mutation error:", checkInMutation.error);
```

## Common Customizations

### Change Step Order
Edit `stepOrder` in CheckinFlow.tsx:
```typescript
const stepOrder: CheckinStep[] = [
  "prefinal",
  "guests",
  "validation",
  "room_change",
  "confirmation"
];
```

### Add Custom Validation Block
In useEffect in CheckinFlow.tsx:
```typescript
const customBlock: ValidationBlock = {
  id: "custom_check",
  label: "Custom Check",
  status: "pass",
  message: "Custom validation message"
};
setValidationBlocks([...mockBlocks, customBlock]);
```

### Change Modal Size
In CheckinFlow.tsx modal className:
```tsx
// Current: max-w-2xl
// Change to: max-w-3xl (larger) or max-w-xl (smaller)
<div className="bg-white rounded-lg shadow-xl max-w-2xl w-full">
```

### Disable Room Change Step
In CheckinFlow.tsx stepOrder:
```typescript
const stepOrder: CheckinStep[] = [
  "prefinal",
  "guests",
  "validation",
  // Remove "room_change",
  "confirmation"
];
```

## Testing Quick Commands

```bash
# Type-check
npx tsc --noEmit

# Format
npx prettier --write "frontend/src/components/CheckinFlow.tsx"

# Test single component
npm test -- CheckinFlow

# Run E2E
npm run e2e
```

## Next: Connect to API

1. Implement 5 endpoints (see `CHECKIN_FLOW_IMPLEMENTATION.md`)
2. Remove mock data from `CheckinFlow.tsx`
3. Use real `useCheckinValidation()` hook
4. Test with actual reservations
5. Deploy to staging

## Support Files

- `CHECKIN_FLOW_IMPLEMENTATION.md` - Full technical reference
- `CHECKIN_SUMMARY.md` - Executive overview
- `frontend/src/types/checkin.ts` - All TypeScript types

---

**Ready to integrate? Start with the router integration in step 1 above!**
