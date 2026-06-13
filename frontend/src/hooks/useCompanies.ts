import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createCompany,
  createCompanyDocument,
  deactivateCompany,
  deleteCompanyDocument,
  listCompanies,
  listCompanyDocuments,
  reactivateCompany,
  updateCompany,
  updateCompanyDocumentStatus,
  type Company,
  type CompanyDocument,
  type CompanyDocumentPayload,
  type CompanyDocumentStatus,
  type CompanyPayload
} from "../api/companies";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

const companiesKey = (hotelId: number | null) => ["companies", hotelId];
const companyDocumentsKey = (hotelId: number | null, companyId: number) => ["company-documents", hotelId, companyId];

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

export function useCompanyMutations() {
  const queryClient = useQueryClient();
  const { session } = useSession();
  const invalidateCompanies = () => queryClient.invalidateQueries({ queryKey: companiesKey(session.hotelId) });

  const createMutation = useMutation({
    mutationFn: (payload: CompanyPayload) => createCompany(payload, session),
    onSuccess: invalidateCompanies
  });

  const updateMutation = useMutation({
    mutationFn: ({ companyId, payload }: { companyId: number; payload: Partial<CompanyPayload> }) =>
      updateCompany(companyId, payload, session),
    onSuccess: invalidateCompanies
  });

  const deactivateMutation = useMutation({
    mutationFn: (companyId: number) => deactivateCompany(companyId, session),
    onSuccess: invalidateCompanies
  });

  const reactivateMutation = useMutation({
    mutationFn: (companyId: number) => reactivateCompany(companyId, session),
    onSuccess: invalidateCompanies
  });

  return { createMutation, updateMutation, deactivateMutation, reactivateMutation };
}

export function useCompanyDocumentMutations(companyId?: number) {
  const queryClient = useQueryClient();
  const { session } = useSession();

  const invalidateDocuments = () => {
    if (companyId) {
      queryClient.invalidateQueries({ queryKey: companyDocumentsKey(session.hotelId, companyId) });
    }
  };

  const createDocumentMutation = useMutation({
    mutationFn: (payload: CompanyDocumentPayload) => createCompanyDocument(payload, session),
    onSuccess: invalidateDocuments
  });

  const updateStatusMutation = useMutation({
    mutationFn: ({ documentId, status }: { documentId: number; status: CompanyDocumentStatus }) =>
      updateCompanyDocumentStatus(documentId, status, session),
    onSuccess: invalidateDocuments
  });

  const deleteDocumentMutation = useMutation({
    mutationFn: (documentId: number) => deleteCompanyDocument(documentId, session),
    onSuccess: invalidateDocuments
  });

  return { createDocumentMutation, updateStatusMutation, deleteDocumentMutation };
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
