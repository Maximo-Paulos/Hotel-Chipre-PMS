import { useRef, useState } from "react";

import { getGuestProhibitedDetail, type RestrictionOverride } from "../api/guestRestrictions";
import { ApiError } from "../api/client";

type Phase = "idle" | "prompting" | "forbidden";

// Drives the "guest is restricted" override confirmation step shared by
// reservation create/update and check-in. Wire it into an existing
// mutation's onError:
//
//   onError: (err) => {
//     if (overridePrompt.handleError(err, (override) => retryWithOverride(override))) return;
//     ...existing generic error handling...
//   }
//
// When the retried request comes back 403 (actor lacks
// reservation:prohibition_override), handleError transitions to "forbidden"
// instead of silently failing or leaving the operator stuck.
export function useRestrictionOverridePrompt() {
  const [phase, setPhase] = useState<Phase>("idle");
  const pendingRef = useRef<{ restrictionId: number; retry: (override: RestrictionOverride) => void } | null>(null);

  const handleError = (error: unknown, retryWithOverride: (override: RestrictionOverride) => void): boolean => {
    const prohibited = getGuestProhibitedDetail(error);
    if (prohibited) {
      pendingRef.current = { restrictionId: prohibited.restriction_id, retry: retryWithOverride };
      setPhase("prompting");
      return true;
    }
    if (error instanceof ApiError && error.status === 403 && pendingRef.current) {
      setPhase("forbidden");
      return true;
    }
    return false;
  };

  const submit = (reason: string) => {
    const pending = pendingRef.current;
    const trimmed = reason.trim();
    if (!pending || !trimmed) return;
    setPhase("idle");
    pending.retry({ restriction_id: pending.restrictionId, reason: trimmed });
  };

  const dismiss = () => {
    setPhase("idle");
    pendingRef.current = null;
  };

  return { phase, handleError, submit, dismiss };
}
