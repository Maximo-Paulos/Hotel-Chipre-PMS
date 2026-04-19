import { apiFetch, type SessionLike } from "./client";

export type OnboardingProviderSetup = {
  enabled: boolean;
  credentials?: Record<string, string>;
  has_credentials?: boolean;
  credential_fields?: string[];
};

export type OnboardingStatus = {
  hotel_id: number;
  completed: boolean;
  steps: Record<string, boolean>;
  missing_steps: string[];
  gates?: {
    can_finish: boolean;
    missing: string[];
  } | null;
  counts: Record<string, number>;
  owner?: Record<string, unknown> | null;
  hotel_identity?: Record<string, unknown> | null;
  deposit_policy?: Record<string, unknown> | null;
  payment_methods?: Record<string, OnboardingProviderSetup> | null;
  ota_channels?: Record<string, OnboardingProviderSetup> | null;
  subscription_choice?: Record<string, unknown> | null;
  current_subscription?: Record<string, unknown> | null;
  categories?: CategoryPayload[];
  rooms?: RoomPayload[];
  staff?: StaffPayload[];
};

export type OwnerPayload = {
  name: string;
  email: string;
  phone?: string | null;
  role?: string | null;
};

export type HotelIdentityPayload = {
  name: string;
  timezone: string;
  currency: string;
  languages: string[];
  jurisdiction_code: string;
};

export type DepositPolicyPayload = {
  deposit_percentage: number;
  free_cancellation_hours: number;
  cancellation_penalty_percentage: number;
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

export type PaymentMethodsPayload = {
  mercado_pago: OnboardingProviderSetup;
  paypal: OnboardingProviderSetup;
  stripe: OnboardingProviderSetup;
};

export type OTAChannelsPayload = {
  booking: OnboardingProviderSetup;
  expedia: OnboardingProviderSetup;
  despegar: OnboardingProviderSetup;
};

export type SubscriptionChoicePayload = {
  plan_code: string;
  start_trial: boolean;
};

export const getOnboardingStatus = (session?: SessionLike) =>
  apiFetch<OnboardingStatus>("/api/onboarding/status", { session });

export const setOwner = (payload: OwnerPayload, session?: SessionLike) =>
  apiFetch<OnboardingStatus>("/api/onboarding/owner", { method: "POST", data: payload, session });

export const setHotelIdentity = (payload: HotelIdentityPayload, session?: SessionLike) =>
  apiFetch<OnboardingStatus>("/api/onboarding/identity", { method: "POST", data: payload, session });

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

export const setDepositPolicy = (payload: DepositPolicyPayload, session?: SessionLike) =>
  apiFetch<OnboardingStatus>("/api/onboarding/policy", {
    method: "POST",
    data: payload,
    session
  });

export const setPaymentMethods = (payload: PaymentMethodsPayload, session?: SessionLike) =>
  apiFetch<OnboardingStatus>("/api/onboarding/payments", {
    method: "POST",
    data: payload,
    session
  });

export const setOtaChannels = (payload: OTAChannelsPayload, session?: SessionLike) =>
  apiFetch<OnboardingStatus>("/api/onboarding/ota", {
    method: "POST",
    data: payload,
    session
  });

export const setSubscriptionChoice = (payload: SubscriptionChoicePayload, session?: SessionLike) =>
  apiFetch<OnboardingStatus>("/api/onboarding/subscription-choice", {
    method: "POST",
    data: payload,
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
