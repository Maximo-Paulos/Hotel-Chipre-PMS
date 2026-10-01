import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createCompany,
  createCompanyDocument,
  deactivateCompany,
  deleteCompanyDocument,
  listCompanies,
  listCompanyDocuments,
  listReservationCompanyDocuments,
  reactivateCompany,
  updateCompany,
  updateCompanyDocumentStatus,
  uploadCompanyDocument,
  markReservationCompanyDocumentSigned,
  type Company,
  type CompanyDocument,
  type CompanyDocumentPayload,
  type CompanyDocumentUploadPayload,
  type CompanyDocumentStatus,
  type CompanyPayload
} from "../api/companies";
import { hasValidSession } from "../api/client";
import { refreshSettingsState } from "../api/queryInvalidation";
import { useSession } from "../state/session";

import { useGuardedMutation } from "./useGuardedMutation";

const companiesKey = (hotelId: number | null) => ["companies", hotelId];
const companyDocumentsKey = (hotelId: number | null, companyId: number) => ["company-documents", hotelId, companyId];
const reservationCompanyDocumentsKey = (hotelId: number | null, reservationId: number) => ["reservation-company-documents", hotelId, reservationId];

export function useCompanies() {
  const { session } = useSession();
  return useQuery<Company[]>({
    queryKey: companiesKey(session.hotelId),
    queryFn: () => listCompanies(session),
    enabled: hasValidSession(session),
    staleTime: 60 * 1000
  });
}

export function useCompanyDocuments(companyId?: number) {
  const { session } = useSession();
  return useQuery<CompanyDocument[]>({
    queryKey: companyId ? companyDocumentsKey(session.hotelId, companyId) : ["company-documents", "none"],
    queryFn: () => listCompanyDocuments(companyId!, session),
    enabled: Boolean(companyId) && hasValidSession(session),
    staleTime: 30 * 1000
  });
}

export function useReservationCompanyDocuments(reservationId?: number) {
  const { session } = useSession();
  return useQuery({
    queryKey: reservationId ? reservationCompanyDocumentsKey(session.hotelId, reservationId) : ["reservation-company-documents", "none"],
    queryFn: () => listReservationCompanyDocuments(reservationId!, session),
    enabled: Boolean(reservationId) && hasValidSession(session),
    staleTime: 30 * 1000
  });
}

export function useMarkCompanyDocumentSigned() {
  const queryClient = useQueryClient();
  const { session } = useSession();
  return useGuardedMutation({
    mutationFn: (documentId: number) => markReservationCompanyDocumentSigned(documentId, session),
    onSuccess: async () => {
      await queryClient.invalidateQueries({ queryKey: ["reservation-company-documents", session.hotelId] });
      await queryClient.invalidateQueries({ queryKey: ["company-documents", session.hotelId] });
    }
  });
}

export function useCompanyMutations() {
  const queryClient = useQueryClient();
  const { session } = useSession();
  const invalidateCompanies = () => refreshSettingsState(queryClient, session.hotelId);

  const createMutation = useGuardedMutation({
    mutationFn: (payload: CompanyPayload) => createCompany(payload, session),
    onSuccess: async () => invalidateCompanies()
  });

  const updateMutation = useGuardedMutation({
    mutationFn: ({ companyId, payload }: { companyId: number; payload: Partial<CompanyPayload> }) =>
      updateCompany(companyId, payload, session),
    onSuccess: async () => invalidateCompanies()
  });

  const deactivateMutation = useGuardedMutation({
    mutationFn: (companyId: number) => deactivateCompany(companyId, session),
    onSuccess: async () => invalidateCompanies()
  });

  const reactivateMutation = useGuardedMutation({
    mutationFn: (companyId: number) => reactivateCompany(companyId, session),
    onSuccess: async () => invalidateCompanies()
  });

  return { createMutation, updateMutation, deactivateMutation, reactivateMutation };
}

export function useCompanyDocumentMutations(companyId?: number) {
  const queryClient = useQueryClient();
  const { session } = useSession();
  void companyId;

  const invalidateDocuments = () => refreshSettingsState(queryClient, session.hotelId);

  const createDocumentMutation = useGuardedMutation({
    mutationFn: (payload: CompanyDocumentPayload) => createCompanyDocument(payload, session),
    onSuccess: async () => invalidateDocuments()
  });

  const uploadDocumentMutation = useGuardedMutation({
    mutationFn: (payload: CompanyDocumentUploadPayload) => uploadCompanyDocument(payload, session),
    onSuccess: async (_document, payload) => {
      await Promise.all([
        invalidateDocuments(),
        queryClient.invalidateQueries({ queryKey: reservationCompanyDocumentsKey(session.hotelId, payload.reservation_id) })
      ]);
    }
  });

  const updateStatusMutation = useGuardedMutation({
    mutationFn: ({ documentId, status }: { documentId: number; status: CompanyDocumentStatus }) =>
      updateCompanyDocumentStatus(documentId, status, session),
    onSuccess: async () => {
      await Promise.all([
        invalidateDocuments(),
        queryClient.invalidateQueries({ queryKey: ["reservation-company-documents", session.hotelId] })
      ]);
    }
  });

  const deleteDocumentMutation = useGuardedMutation({
    mutationFn: (documentId: number) => deleteCompanyDocument(documentId, session),
    onSuccess: async () => {
      await Promise.all([
        invalidateDocuments(),
        queryClient.invalidateQueries({ queryKey: ["reservation-company-documents", session.hotelId] })
      ]);
    }
  });

  return { createDocumentMutation, uploadDocumentMutation, updateStatusMutation, deleteDocumentMutation };
}

export const companyDocumentTypeLabel: Record<string, string> = {
  voucher_pdf: "Voucher PDF",
  signature_required: "Firma requerida",
  authorization: "Autorizacion",
  extension: "Extension",
  other: "Otro"
};

export const companyDocumentStatusLabel: Record<string, string> = {
  pending: "Pendiente",
  signed: "Firmado",
  waived: "Eximido",
  rejected: "Rechazado"
};
