import type { OwnerPayload } from "../api/onboarding";

const PENDING_OWNER_KEY = "hotel-pms-pending-owner";

export const storePendingOwner = (owner: OwnerPayload) => {
  if (typeof sessionStorage === "undefined") return;
  sessionStorage.setItem(PENDING_OWNER_KEY, JSON.stringify(owner));
};

export const getPendingOwner = (): OwnerPayload | null => {
  if (typeof sessionStorage === "undefined") return null;
  try {
    const raw = sessionStorage.getItem(PENDING_OWNER_KEY);
    if (!raw) return null;
    const parsed = JSON.parse(raw) as Partial<OwnerPayload>;
    if (typeof parsed.name !== "string" || typeof parsed.email !== "string") return null;
    return {
      name: parsed.name,
      email: parsed.email,
      phone: typeof parsed.phone === "string" ? parsed.phone : "",
      role: typeof parsed.role === "string" ? parsed.role : "Owner"
    };
  } catch {
    return null;
  }
};

export const clearPendingOwner = () => {
  if (typeof sessionStorage === "undefined") return;
  sessionStorage.removeItem(PENDING_OWNER_KEY);
};
