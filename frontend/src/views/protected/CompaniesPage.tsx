import React, { useEffect, useMemo, useState } from "react";

import {
  type Company,
  type CompanyDocumentPayload,
  type CompanyDocumentStatus,
  type CompanyDocumentType,
  type CompanyPayload,
  fetchCompanyDocumentFile
} from "../../api/companies";
import {
  companyDocumentStatusLabel,
  companyDocumentTypeLabel,
  useCompanies,
  useCompanyDocumentMutations,
  useCompanyDocuments,
  useCompanyMutations
} from "../../hooks/useCompanies";
import { useHotelConfig } from "../../hooks/useHotelConfig";
import { formatHotelDateTime } from "../../utils/date";
import { useSession } from "../../state/session";

const documentTypes: CompanyDocumentType[] = ["voucher_pdf", "signature_required", "authorization", "extension", "other"];
const signatureStatuses: CompanyDocumentStatus[] = ["pending", "signed", "waived", "rejected"];

const emptyCompanyForm: CompanyPayload = {
  legal_name: "",
  display_name: "",
  tax_id: "",
  country_code: "AR",
  contact_name: "",
  email: "",
  phone: "",
  administrative_contact: "",
  base_price: null,
  extra_person_nightly_surcharge: null,
  payment_deferred: false,
  deferred_days: 0,
  requires_voucher: false,
  requires_signature: false,
  notes: ""
};

const emptyDocumentForm: CompanyDocumentPayload = {
  reservation_id: 0,
  company_id: null,
  doc_type: "voucher_pdf",
  file_name: "",
  file_url: "",
  requires_signature: true,
  notes: ""
};

export function CompaniesPage() {
  const { session } = useSession();
  const hotelConfigQuery = useHotelConfig();
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [companyForm, setCompanyForm] = useState<CompanyPayload>(emptyCompanyForm);
  const [documentForm, setDocumentForm] = useState<CompanyDocumentPayload>(emptyDocumentForm);
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [companyMessage, setCompanyMessage] = useState<string | null>(null);
  const [documentMessage, setDocumentMessage] = useState<string | null>(null);

  const companiesQuery = useCompanies();
  const companies = useMemo(() => companiesQuery.data ?? [], [companiesQuery.data]);
  const selectedCompany = useMemo(
    () => companies.find((company) => company.id === selectedCompanyId) ?? companies[0] ?? null,
    [companies, selectedCompanyId]
  );
  const documentsQuery = useCompanyDocuments(selectedCompany?.id);
  const companyMutations = useCompanyMutations();
  const documentMutations = useCompanyDocumentMutations(selectedCompany?.id);

  useEffect(() => {
    if (!selectedCompany) {
      setSelectedCompanyId(null);
      setCompanyForm(emptyCompanyForm);
      setDocumentForm(emptyDocumentForm);
      setDocumentFile(null);
      return;
    }
    setSelectedCompanyId(selectedCompany.id);
    setCompanyForm({
      legal_name: selectedCompany.legal_name,
      display_name: selectedCompany.display_name,
      tax_id: selectedCompany.tax_id ?? "",
      country_code: selectedCompany.country_code ?? "AR",
      contact_name: selectedCompany.contact_name ?? "",
      email: selectedCompany.email ?? "",
      phone: selectedCompany.phone ?? "",
      administrative_contact: selectedCompany.administrative_contact ?? "",
      base_price: selectedCompany.base_price == null ? null : Number(selectedCompany.base_price),
      extra_person_nightly_surcharge: selectedCompany.extra_person_nightly_surcharge == null
        ? null
        : Number(selectedCompany.extra_person_nightly_surcharge),
      payment_deferred: selectedCompany.payment_deferred,
      deferred_days: selectedCompany.deferred_days ?? 0,
      requires_voucher: selectedCompany.requires_voucher,
      requires_signature: selectedCompany.requires_signature,
      notes: selectedCompany.notes ?? ""
    });
    setDocumentForm((current) => ({ ...current, company_id: selectedCompany.id }));
  }, [selectedCompany]);

  const resetForNewCompany = () => {
    setSelectedCompanyId(null);
    setCompanyForm(emptyCompanyForm);
    setCompanyMessage(null);
  };

  const handleCompanyChange = (field: keyof CompanyPayload, value: string | number | boolean | null) => {
    setCompanyForm((current) => ({ ...current, [field]: value }));
  };

  const handleDocumentChange = (field: keyof CompanyDocumentPayload, value: string | number | boolean) => {
    setDocumentForm((current) => ({ ...current, [field]: value }));
  };

  const cleanCompanyPayload = (): CompanyPayload => ({
    legal_name: companyForm.legal_name.trim(),
    display_name: companyForm.display_name.trim(),
    tax_id: companyForm.tax_id?.trim() || null,
    country_code: companyForm.country_code?.trim().toUpperCase() || null,
    contact_name: companyForm.contact_name?.trim() || null,
    email: companyForm.email?.trim() || null,
    phone: companyForm.phone?.trim() || null,
    administrative_contact: companyForm.administrative_contact?.trim() || null,
    base_price: companyForm.payment_deferred ? null : companyForm.base_price,
    extra_person_nightly_surcharge: companyForm.extra_person_nightly_surcharge,
    payment_deferred: Boolean(companyForm.payment_deferred),
    deferred_days: Number(companyForm.deferred_days ?? 0),
    requires_voucher: Boolean(companyForm.requires_voucher),
    requires_signature: Boolean(companyForm.requires_signature),
    notes: companyForm.notes?.trim() || null
  });

  const handleCompanySubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCompanyMessage(null);
    try {
      const payload = cleanCompanyPayload();
      const saved = selectedCompanyId
        ? await companyMutations.updateMutation.mutateAsync({ companyId: selectedCompanyId, payload })
        : await companyMutations.createMutation.mutateAsync(payload);
      setSelectedCompanyId(saved.id);
      setCompanyMessage("Empresa guardada.");
    } catch (error) {
      setCompanyMessage(error instanceof Error ? error.message : "No se pudo guardar la empresa.");
    }
  };

  const handleActiveToggle = async (company: Company) => {
    setCompanyMessage(null);
    try {
      if (company.is_active) {
        await companyMutations.deactivateMutation.mutateAsync(company.id);
        setCompanyMessage("Empresa desactivada.");
      } else {
        await companyMutations.reactivateMutation.mutateAsync(company.id);
        setCompanyMessage("Empresa reactivada.");
      }
    } catch (error) {
      setCompanyMessage(error instanceof Error ? error.message : "No se pudo cambiar el estado.");
    }
  };

  const handleDocumentSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selectedCompany || !documentFile) return;
    setDocumentMessage(null);
    try {
      const contentBase64 = await new Promise<string>((resolve, reject) => {
        const reader = new FileReader();
        reader.onload = () => resolve(String(reader.result || ""));
        reader.onerror = () => reject(reader.error || new Error("No se pudo leer el archivo."));
        reader.readAsDataURL(documentFile);
      });
      await documentMutations.uploadDocumentMutation.mutateAsync({
        company_id: selectedCompany.id,
        reservation_id: Number(documentForm.reservation_id),
        doc_type: documentForm.doc_type ?? "voucher_pdf",
        file_name: documentFile.name,
        content_base64: contentBase64,
        requires_signature: Boolean(documentForm.requires_signature),
        notes: documentForm.notes?.trim() || null
      });
      setDocumentForm({ ...emptyDocumentForm, company_id: selectedCompany.id });
      setDocumentFile(null);
      setDocumentMessage("PDF cargado en almacenamiento privado.");
    } catch (error) {
      setDocumentMessage(error instanceof Error ? error.message : "No se pudo subir el PDF.");
    }
  };

  const handleOpenDocument = async (documentId: number) => {
    setDocumentMessage(null);
    try {
      const url = await fetchCompanyDocumentFile(documentId, session);
      const link = document.createElement("a");
      link.href = url;
      link.target = "_blank";
      link.rel = "noopener noreferrer";
      link.click();
      window.setTimeout(() => URL.revokeObjectURL(url), 60_000);
    } catch (error) {
      setDocumentMessage(error instanceof Error ? error.message : "No se pudo abrir el PDF.");
    }
  };

  const handleStatusChange = async (documentId: number, status: CompanyDocumentStatus) => {
    setDocumentMessage(null);
    try {
      await documentMutations.updateStatusMutation.mutateAsync({ documentId, status });
      setDocumentMessage("Estado de firma actualizado.");
    } catch (error) {
      setDocumentMessage(error instanceof Error ? error.message : "No se pudo actualizar el estado.");
    }
  };

  const handleDocumentDelete = async (documentId: number) => {
    setDocumentMessage(null);
    try {
      await documentMutations.deleteDocumentMutation.mutateAsync(documentId);
      setDocumentMessage("Documento eliminado.");
    } catch (error) {
      setDocumentMessage(error instanceof Error ? error.message : "No se pudo eliminar el documento.");
    }
  };

  const documents = documentsQuery.data ?? [];
  const companyBusy =
    companyMutations.createMutation.isPending ||
    companyMutations.updateMutation.isPending ||
    companyMutations.deactivateMutation.isPending ||
    companyMutations.reactivateMutation.isPending;
  const documentBusy =
    documentMutations.createDocumentMutation.isPending ||
    documentMutations.uploadDocumentMutation.isPending ||
    documentMutations.updateStatusMutation.isPending ||
    documentMutations.deleteDocumentMutation.isPending;

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Configuración</p>
          <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">Empresas</h1>
          <p className="text-sm text-slate-600">Gestion de cuentas corporativas, vouchers y documentos con firma.</p>
        </div>
        <button
          type="button"
          onClick={resetForNewCompany}
          className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
        >
          Nueva empresa
        </button>
      </header>

      <div className="grid gap-4 lg:grid-cols-[340px_minmax(0,1fr)]">
        <section className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
          <div className="border-b border-slate-200 px-4 py-3">
            <p className="text-xs uppercase tracking-wide text-slate-500">Listado</p>
            <h2 className="text-lg font-semibold text-slate-900">Empresas ({companies.length})</h2>
            {companiesQuery.error && <p className="text-xs text-rose-700">No se pudo cargar: {(companiesQuery.error as Error).message}</p>}
          </div>
          <div className="max-h-[65vh] overflow-y-auto">
            {companiesQuery.isLoading ? (
              <p className="px-4 py-3 text-sm text-slate-500">Cargando empresas...</p>
            ) : companies.length === 0 ? (
              <p className="px-4 py-3 text-sm text-slate-500">No hay empresas cargadas.</p>
            ) : (
              <div className="divide-y divide-slate-200">
                {companies.map((company) => {
                  const isActive = company.id === selectedCompany?.id;
                  return (
                    <button
                      key={company.id}
                      type="button"
                      onClick={() => setSelectedCompanyId(company.id)}
                      className={`w-full px-4 py-3 text-left hover:bg-slate-50 ${isActive ? "bg-brand-50" : "bg-white"}`}
                    >
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <p className="font-semibold text-slate-900">{company.display_name}</p>
                          <p className="text-xs text-slate-500">{company.tax_id || company.legal_name}</p>
                        </div>
                        <span className={`rounded-full px-2 py-1 text-[11px] font-semibold ${company.is_active ? "bg-emerald-100 text-emerald-800" : "bg-slate-100 text-slate-600"}`}>
                          {company.is_active ? "Activa" : "Inactiva"}
                        </span>
                      </div>
                    </button>
                  );
                })}
              </div>
            )}
          </div>
        </section>

        <section className="space-y-4 rounded-xl border border-slate-200 bg-white p-5 shadow-sm">
          <form className="space-y-4" onSubmit={handleCompanySubmit}>
            <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">Ficha corporativa</p>
                <h2 className="text-lg font-semibold text-slate-900">
                  {selectedCompany ? selectedCompany.display_name : "Nueva empresa"}
                </h2>
                <p className="text-xs text-slate-500">
                  {selectedCompany?.updated_at ? `Actualizada ${formatHotelDateTime(selectedCompany.updated_at, hotelConfigQuery.data?.hotel_timezone)}` : "Sin guardar"}
                </p>
              </div>
              {selectedCompany ? (
                <button
                  type="button"
                  disabled={companyBusy}
                  onClick={() => handleActiveToggle(selectedCompany)}
                  className="rounded-lg border border-slate-200 bg-white px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60"
                >
                  {selectedCompany.is_active ? "Desactivar" : "Reactivar"}
                </button>
              ) : null}
            </div>

            <div className="grid gap-4 md:grid-cols-2">
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Nombre legal</span>
                <input
                  value={companyForm.legal_name}
                  onChange={(event) => handleCompanyChange("legal_name", event.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Nombre comercial</span>
                <input
                  value={companyForm.display_name}
                  onChange={(event) => handleCompanyChange("display_name", event.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">CUIT / Tax ID</span>
                <input
                  value={companyForm.tax_id ?? ""}
                  onChange={(event) => handleCompanyChange("tax_id", event.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">País</span>
                <input
                  value={companyForm.country_code ?? ""}
                  maxLength={2}
                  onChange={(event) => handleCompanyChange("country_code", event.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2 uppercase"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Contacto</span>
                <input
                  value={companyForm.contact_name ?? ""}
                  onChange={(event) => handleCompanyChange("contact_name", event.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Email de contacto</span>
                <input
                  type="email"
                  value={companyForm.email ?? ""}
                  onChange={(event) => handleCompanyChange("email", event.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Teléfono</span>
                <input
                  value={companyForm.phone ?? ""}
                  onChange={(event) => handleCompanyChange("phone", event.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Contacto administrativo</span>
                <input
                  value={companyForm.administrative_contact ?? ""}
                  onChange={(event) => handleCompanyChange("administrative_contact", event.target.value)}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-700 md:col-span-2">
                <input
                  type="checkbox"
                  checked={Boolean(companyForm.payment_deferred)}
                  onChange={(event) => handleCompanyChange("payment_deferred", event.target.checked)}
                />
                La empresa paga su factura fuera del PMS, después de la estadía
              </label>
              {companyForm.payment_deferred ? (
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Vencimiento de factura (días después del check-out)</span>
                  <input
                    type="number"
                    min={0}
                    max={365}
                    value={companyForm.deferred_days ?? 0}
                    onChange={(event) => handleCompanyChange("deferred_days", Number(event.target.value || 0))}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  />
                </label>
              ) : (
                <label className="space-y-1 text-sm">
                  <span className="text-slate-600">Tarifa base acordada</span>
                  <input
                    type="number"
                    min={0}
                    step="0.01"
                    value={companyForm.base_price ?? ""}
                    onChange={(event) => handleCompanyChange("base_price", event.target.value === "" ? null : Number(event.target.value))}
                    className="w-full rounded-lg border border-slate-300 px-3 py-2"
                  />
                </label>
              )}
              <label className="space-y-1 text-sm">
                <span className="text-slate-600">Adicional por huésped extra y noche</span>
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  value={companyForm.extra_person_nightly_surcharge ?? ""}
                  onChange={(event) => handleCompanyChange("extra_person_nightly_surcharge", event.target.value === "" ? null : Number(event.target.value))}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
                <span className="block text-xs font-normal text-slate-500">Lo configura Gerencia; Recepción solo registra el cobro de las noches elegidas.</span>
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-700 md:col-span-2">
                <input
                  type="checkbox"
                  checked={Boolean(companyForm.requires_voucher)}
                  onChange={(event) => handleCompanyChange("requires_voucher", event.target.checked)}
                />
                Exigir voucher cargado en cada reserva
              </label>
              <label className="flex items-center gap-2 text-sm text-slate-700 md:col-span-2">
                <input
                  type="checkbox"
                  checked={Boolean(companyForm.requires_signature)}
                  onChange={(event) => handleCompanyChange("requires_signature", event.target.checked)}
                />
                Exigir documento de la empresa firmado antes del check-in
              </label>
              <label className="space-y-1 text-sm md:col-span-2">
                <span className="text-slate-600">Descripción y preferencias de habitación</span>
                <textarea
                  value={companyForm.notes ?? ""}
                  onChange={(event) => handleCompanyChange("notes", event.target.value)}
                  rows={3}
                  className="w-full rounded-lg border border-slate-300 px-3 py-2"
                />
              </label>
            </div>

            {companyMessage ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{companyMessage}</div>
            ) : null}

            <div className="flex justify-end">
              <button
                type="submit"
                disabled={companyBusy || !companyForm.legal_name.trim() || !companyForm.display_name.trim()}
                className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
              >
                {companyBusy ? "Guardando..." : "Guardar empresa"}
              </button>
            </div>
          </form>

          <section className="space-y-4 border-t border-slate-200 pt-4">
            <div>
              <p className="text-xs uppercase tracking-wide text-slate-500">Documentos</p>
              <h3 className="text-base font-semibold text-slate-900">Vouchers y firmas</h3>
            </div>

            {selectedCompany ? (
              <>
                <div className="rounded-lg border border-slate-200 bg-slate-50 p-4">
                  {documentsQuery.isLoading ? (
                    <p className="text-sm text-slate-500">Cargando documentos...</p>
                  ) : documents.length === 0 ? (
                    <p className="text-sm text-slate-500">No hay documentos asociados a esta empresa.</p>
                  ) : (
                    <div className="space-y-3">
                      {documents.map((document) => (
                        <div key={document.id} className="rounded-lg border border-slate-200 bg-white p-3 shadow-sm">
                          <div className="flex flex-col gap-3 sm:flex-row sm:items-start sm:justify-between">
                            <div>
                              <p className="font-semibold text-slate-900">{document.file_name || `Documento #${document.id}`}</p>
                              <p className="text-xs text-slate-500">
                                Reserva #{document.reservation_id} - {companyDocumentTypeLabel[document.doc_type] || document.doc_type}
                              </p>
                              {document.stored_object_id ? (
                                <button type="button" className="text-xs font-semibold text-brand-700 underline" onClick={() => void handleOpenDocument(document.id)}>
                                  Abrir archivo privado
                                </button>
                              ) : null}
                            </div>
                            <div className="flex flex-col gap-2 sm:w-48">
                              <select
                                value={document.status}
                                disabled={documentBusy}
                                onChange={(event) => handleStatusChange(document.id, event.target.value as CompanyDocumentStatus)}
                                className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800"
                              >
                                {signatureStatuses.map((status) => (
                                  <option key={status} value={status}>
                                    {companyDocumentStatusLabel[status]}
                                  </option>
                                ))}
                              </select>
                              <button
                                type="button"
                                disabled={documentBusy}
                                onClick={() => handleDocumentDelete(document.id)}
                                className="rounded-lg border border-rose-200 bg-white px-3 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-60"
                              >
                                Eliminar
                              </button>
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                <form className="grid gap-4 md:grid-cols-2" onSubmit={handleDocumentSubmit}>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Reserva ID</span>
                    <input
                      type="number"
                      min={1}
                      value={documentForm.reservation_id || ""}
                      onChange={(event) => handleDocumentChange("reservation_id", Number(event.target.value))}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Tipo</span>
                    <select
                      value={documentForm.doc_type}
                      onChange={(event) => handleDocumentChange("doc_type", event.target.value as CompanyDocumentType)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    >
                      {documentTypes.map((type) => (
                        <option key={type} value={type}>
                          {companyDocumentTypeLabel[type]}
                        </option>
                      ))}
                    </select>
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-600">Voucher o documento PDF (máximo 5 MB)</span>
                    <input
                      type="file"
                      accept="application/pdf,.pdf"
                      onChange={(event) => setDocumentFile(event.target.files?.[0] ?? null)}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>
                  <label className="flex items-center gap-2 text-sm text-slate-700">
                    <input
                      type="checkbox"
                      checked={Boolean(documentForm.requires_signature)}
                      onChange={(event) => handleDocumentChange("requires_signature", event.target.checked)}
                    />
                    Requiere firma
                  </label>
                  <label className="space-y-1 text-sm md:col-span-2">
                    <span className="text-slate-600">Notas</span>
                    <textarea
                      value={documentForm.notes ?? ""}
                      onChange={(event) => handleDocumentChange("notes", event.target.value)}
                      rows={3}
                      className="w-full rounded-lg border border-slate-300 px-3 py-2"
                    />
                  </label>

                  {documentMessage ? (
                    <div className="md:col-span-2 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">
                      {documentMessage}
                    </div>
                  ) : null}

                  <div className="md:col-span-2 flex justify-end">
                    <button
                      type="submit"
                      disabled={documentBusy || !documentForm.reservation_id || !documentFile}
                      className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                    >
                      {documentBusy ? "Subiendo..." : "Subir PDF privado"}
                    </button>
                  </div>
                </form>
              </>
            ) : (
              <div className="rounded-lg border border-dashed border-slate-300 bg-slate-50 px-4 py-6 text-sm text-slate-500">
                Selecciona o crea una empresa para administrar documentos.
              </div>
            )}
          </section>
        </section>
      </div>
    </div>
  );
}
