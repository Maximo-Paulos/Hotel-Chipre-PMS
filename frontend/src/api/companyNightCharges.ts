import { apiFetch, type SessionLike } from "./client";

export type CompanyNightCharge = {
  id: number;
  stay_date: string;
  amount: number;
  currency_code: string;
  paid_amount: number;
  remaining_due: number;
  payment_pending: boolean;
  review_only: boolean;
};

export type CompanyNightChargesSummary = {
  reservation_id: number;
  company_id: number;
  currency_code: string;
  nightly_surcharge_amount: number | null;
  charges: CompanyNightCharge[];
};

export const getCompanyNightCharges = (reservationId: number, session?: SessionLike) =>
  apiFetch<CompanyNightChargesSummary>(`/api/reservations/${reservationId}/company-night-charges`, { session });

export const createCompanyNightCharges = (
  reservationId: number,
  stayDates: string[],
  session?: SessionLike
) => apiFetch<CompanyNightChargesSummary>(`/api/reservations/${reservationId}/company-night-charges`, {
  method: "POST",
  data: { stay_dates: stayDates },
  session
});
