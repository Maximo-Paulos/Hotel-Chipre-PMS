import { apiFetch, type SessionLike } from "./client";

export type Company = {
  id: number;
  hotel_id: number;
  legal_name: string;
  display_name: string;
  tax_id?: string | null;
  country_code?: string | null;
  notes?: string | null;
  is_active: boolean;
  created_at: string;
  updated_at: string;
  deactivated_at?: string | null;
  deactivated_by_user_id?: number | null;
};

export type CompanyPayload = {
  legal_name: string;
  display_name: string;
  tax_id?: string | null;
  country_code?: string | null;
  notes?: string | null;
};

export type CompanyDocumentType =
  | "voucher_pdf"
  | "signature_required"
  | "authorization"
  | "extension"
  | "other";

export type CompanyDocumentStatus = "pending" | "signed" | "waived" | "rejected";

export type CompanyDocument = {
  id: number;
  hotel_id: number;
  reservation_id: number;
  company_id?: number | null;
  doc_type: CompanyDocumentType;
  status: CompanyDocumentStatus;
  file_name?: string | null;
  file_url?: string | null;
  requires_signature: boolean;
  signed_at?: string | null;
  signed_by_user_id?: number | null;
  notes?: string | null;
  created_at: string;
  updated_at: string;
  created_by_user_id?: number | null;
};

export type CompanyDocumentPayload = {
  reservation_id: number;
  company_id?: number | null;
  doc_type?: CompanyDocumentType;
  file_name?: string | null;
  file_url?: string | null;
  requires_signature?: boolean;
  notes?: string | null;
};

export const listCompanies = (session?: SessionLike) =>
  apiFetch<Company[]>("/api/companies", { session });

export const createCompany = (payload: CompanyPayload, session?: SessionLike) =>
  apiFetch<Company>("/api/companies", { method: "POST", data: payload, session });

export const updateCompany = (companyId: number, payload: Partial<CompanyPayload>, session?: SessionLike) =>
  apiFetch<Company>(`/api/companies/${companyId}`, { method: "PATCH", data: payload, session });

export const deactivateCompany = (companyId: number, session?: SessionLike) =>
  apiFetch<Company>(`/api/companies/${companyId}/deactivate`, { method: "POST", session });

export const reactivateCompany = (companyId: number, session?: SessionLike) =>
  apiFetch<Company>(`/api/companies/${companyId}/reactivate`, { method: "POST", session });

export const listCompanyDocuments = (companyId: number, session?: SessionLike) =>
  apiFetch<CompanyDocument[]>(`/api/company-documents/company/${companyId}`, { session });

export const createCompanyDocument = (payload: CompanyDocumentPayload, session?: SessionLike) =>
  apiFetch<CompanyDocument>("/api/company-documents", { method: "POST", data: payload, session });

export const updateCompanyDocumentStatus = (
  documentId: number,
  status: CompanyDocumentStatus,
  session?: SessionLike
) =>
  apiFetch<CompanyDocument>(`/api/company-documents/${documentId}/status`, {
    method: "PATCH",
    data: { status },
    session
  });

export const deleteCompanyDocument = (documentId: number, session?: SessionLike) =>
  apiFetch<null>(`/api/company-documents/${documentId}`, { method: "DELETE", session });
