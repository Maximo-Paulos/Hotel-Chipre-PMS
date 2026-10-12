import { apiFetch, type SessionLike } from "./client";

export type TaxRule = {
  id?: number;
  channel_code?: string | null;
  guest_scope: "all" | "local" | "foreign";
  tax_code: string;
  tax_name: string;
  tax_type: "percentage" | "fixed";
  amount: number;
  currency_code?: string | null;
  priority: number;
  applies_when_json?: string | null;
  is_active: boolean;
};

export type TaxPolicy = {
  id: number;
  code: string;
  name: string;
  taxes_included: boolean;
  apply_vat_by_default: boolean;
  vat_rate: number | null;
  foreign_guest_tax_exempt: boolean;
  is_active: boolean;
  metadata_json?: string | null;
  rules: TaxRule[];
};

export type TaxPolicyWrite = Omit<TaxPolicy, "id" | "rules"> & { rules: TaxRule[] };

export const listTaxPolicies = (session?: SessionLike) =>
  apiFetch<TaxPolicy[]>("/api/commercial/tax-policies", { session });

export const createTaxPolicy = (payload: TaxPolicyWrite, session?: SessionLike) =>
  apiFetch<TaxPolicy>("/api/commercial/tax-policies", { method: "POST", data: payload, session });

export const updateTaxPolicy = (id: number, payload: TaxPolicyWrite, session?: SessionLike) =>
  apiFetch<TaxPolicy>(`/api/commercial/tax-policies/${id}`, { method: "PATCH", data: payload, session });
