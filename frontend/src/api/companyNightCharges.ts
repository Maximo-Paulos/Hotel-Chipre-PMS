import { apiFetch, type SessionLike } from "./client";

export type CompanyNightChargeAmount = number | string;

export type CompanyNightCharge = {
  id: number;
  stay_date: string;
  amount: CompanyNightChargeAmount;
  unit_amount: CompanyNightChargeAmount;
  quantity: number;
  rate_effective_from: string | null;
  currency_code: string;
  paid_amount: CompanyNightChargeAmount;
  remaining_due: CompanyNightChargeAmount;
  payment_pending: boolean;
  review_only: boolean;
  adjustments: CompanyNightChargeAmountAdjustment[];
};

export type CompanyNightChargeAmountAdjustment = {
  id: number;
  previous_amount: CompanyNightChargeAmount;
  new_amount: CompanyNightChargeAmount;
  delta_amount: CompanyNightChargeAmount;
  reason: string;
  created_by_user_id: number | null;
  created_at: string;
};

export type CompanyNightChargesSummary = {
  reservation_id: number;
  company_id: number;
  currency_code: string;
  nightly_surcharge_amount: CompanyNightChargeAmount | null;
  charges: CompanyNightCharge[];
};

export const getCompanyNightCharges = (reservationId: number, session?: SessionLike) =>
  apiFetch<CompanyNightChargesSummary>(`/api/reservations/${reservationId}/company-night-charges`, { session });

export const createCompanyNightCharges = (
  reservationId: number,
  stayDates: string[],
  session?: SessionLike,
  extraPersonCount = 1
) => apiFetch<CompanyNightChargesSummary>(`/api/reservations/${reservationId}/company-night-charges`, {
  method: "POST",
  data: { stay_dates: stayDates, extra_person_count: extraPersonCount },
  session
});

export type CompanyNightChargeCorrection = {
  charge_id: number;
  new_amount: number;
  reason: string;
};

export const correctCompanyNightChargeAmounts = (
  reservationId: number,
  items: CompanyNightChargeCorrection[],
  session?: SessionLike
) => apiFetch<CompanyNightChargesSummary>(
  `/api/reservations/${reservationId}/company-night-charges/corrections`,
  {
    method: "POST",
    data: { items },
    session
  }
);
