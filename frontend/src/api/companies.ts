import { API_BASE, apiFetch, buildAuthHeaders, type SessionLike } from "./client";

export type Company = {
  id: number;
  hotel_id: number;
  legal_name: string;
  display_name: string;
  tax_id?: string | null;
  country_code?: string | null;
  contact_name?: string | null;
  email?: string | null;
  phone?: string | null;
  administrative_contact?: string | null;
  base_price?: string | null;
  extra_person_nightly_surcharge?: string | null;
  payment_deferred: boolean;
  deferred_days: number;
  requires_voucher: boolean;
  requires_signature: boolean;
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
  contact_name?: string | null;
  email?: string | null;
  phone?: string | null;
  administrative_contact?: string | null;
  base_price?: number | null;
  extra_person_nightly_surcharge?: number | null;
  payment_deferred?: boolean;
  deferred_days?: number;
  requires_voucher?: boolean;
  requires_signature?: boolean;
  notes?: string | null;
};

export type CompanyOption = {
  id: number;
  display_name: string;
  legal_name: string;
  is_active: boolean;
  payment_deferred: boolean;
};

export const listCompanyOptions = (session?: SessionLike) =>
  apiFetch<CompanyOption[]>("/api/companies/options", { session });

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
  stored_object_id?: string | null;
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

export type CompanyDocumentUploadPayload = {
  reservation_id: number;
  company_id?: number | null;
  doc_type: CompanyDocumentType;
  file_name: string;
  content_base64: string;
  requires_signature?: boolean;
  notes?: string | null;
};

export const uploadCompanyDocument = (payload: CompanyDocumentUploadPayload, session?: SessionLike) =>
  apiFetch<CompanyDocument>("/api/company-documents/upload", { method: "POST", data: payload, session });

export const fetchCompanyDocumentFile = async (documentId: number, session?: SessionLike) => {
  const response = await fetch(`${API_BASE}/company-documents/${documentId}/file`, {
    headers: buildAuthHeaders(session),
    credentials: "include"
  });
  if (!response.ok) throw new Error("No se pudo abrir el documento.");
  return URL.createObjectURL(await response.blob());
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

export const listReservationCompanyDocuments = (reservationId: number, session?: SessionLike) =>
  apiFetch<CompanyDocument[]>(`/api/company-documents/reservation/${reservationId}`, { session });

export const markReservationCompanyDocumentSigned = (documentId: number, session?: SessionLike) =>
  apiFetch<CompanyDocument>(`/api/company-documents/${documentId}/mark-signed`, { method: "POST", session });

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
