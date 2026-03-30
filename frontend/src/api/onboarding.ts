import { apiFetch, type SessionLike } from "./client";

export type OnboardingStatus = {
  hotel_id: number;
  completed: boolean;
  steps: Record<string, boolean>;
  missing_steps: string[];
  counts: Record<string, number>;
  owner?: Record<string, unknown> | null;
};

export type OwnerPayload = {
  name: string;
  email: string;
  phone?: string | null;
  role?: string | null;
};

export type CategoryPayload = {
  name: string;
  code: string;
  description?: string;
  base_price_per_night: number;
  max_occupancy: number;
  amenities?: string;
};

export type RoomPayload = {
  room_number: string;
  floor: number;
  category_code: string;
};

export type StaffPayload = {
  name: string;
  role?: string;
  email?: string;
  phone?: string;
};

export const getOnboardingStatus = (session?: SessionLike) =>
  apiFetch<OnboardingStatus>("/api/onboarding/status", { session });

export const setOwner = (payload: OwnerPayload, session?: SessionLike) =>
  apiFetch<OnboardingStatus>("/api/onboarding/owner", { method: "POST", data: payload, session });

export const setCategories = (categories: CategoryPayload[], session?: SessionLike) =>
  apiFetch<OnboardingStatus>("/api/onboarding/categories", {
    method: "POST",
    data: { categories },
    session
  });

export const setRooms = (rooms: RoomPayload[], session?: SessionLike) =>
  apiFetch<OnboardingStatus>("/api/onboarding/rooms", {
    method: "POST",
    data: { rooms },
    session
  });

export const setStaff = (staff: StaffPayload[], session?: SessionLike) =>
  apiFetch<OnboardingStatus>("/api/onboarding/staff", {
    method: "POST",
    data: { staff },
    session
  });

export const finishOnboarding = (session?: SessionLike) =>
  apiFetch<OnboardingStatus>("/api/onboarding/finish", {
    method: "POST",
    session
  });
