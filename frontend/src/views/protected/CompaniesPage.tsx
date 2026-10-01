import React, { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import {
  type Company,
  type CompanyDocumentPayload,
  type CompanyDocumentStatus,
  type CompanyDocumentType,
  type CompanyNightlyRatesResponse,
  type CompanyPayload,
  createCompanyNightlyRate,
  fetchCompanyDocumentFile,
  listCompanyNightlyRates
} from "../../api/companies";
import { hasValidSession } from "../../api/client";
import {
  companyDocumentStatusLabel,
  companyDocumentTypeLabel,
  useCompanies,
  useCompanyDocumentMutations,
  useCompanyDocuments,
  useCompanyMutations
} from "../../hooks/useCompanies";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";
import { useHotelConfig } from "../../hooks/useHotelConfig";
import { formatHotelDateTime } from "../../utils/date";
import { interfaceLanguageToLocale } from "../../i18n";
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

function formatRateDate(value: string, locale: string): string {
  const [year, month, day] = value.split("-").map(Number);
  return new Intl.DateTimeFormat(locale, { dateStyle: "medium", timeZone: "UTC" }).format(
    new Date(Date.UTC(year, month - 1, day))
  );
}

function formatNightlyRateAmount(amount: number | string, currencyCode: string | undefined, locale: string): string {
  const numericAmount = Number(amount);
  const safeAmount = Number.isFinite(numericAmount) ? numericAmount : 0;
  if (!currencyCode) {
    return new Intl.NumberFormat(locale, { minimumFractionDigits: 2, maximumFractionDigits: 2 }).format(safeAmount);
  }
  try {
    return new Intl.NumberFormat(locale, {
      style: "currency",
      currency: currencyCode,
      minimumFractionDigits: 2,
      maximumFractionDigits: 2
    }).format(safeAmount);
  } catch {
    return `${numericAmount.toFixed(2)} ${currencyCode}`;
  }
}

export function CompaniesPage() {
  const { session } = useSession();
  const { t, i18n } = useTranslation("companies");
  const hotelConfigQuery = useHotelConfig();
  const queryClient = useQueryClient();
  const { hasPermission, hasAllPermissions, permissionsKnown } = useEffectivePermissions();
  const canManageCompanies = permissionsKnown && hasPermission("company:manage");
  const canManageNightlyRates = permissionsKnown && hasAllPermissions([
    "company:manage",
    "company:night_rate_manage"
  ]);
  const locale = interfaceLanguageToLocale(i18n.language);
  const currencyCode = hotelConfigQuery.data?.default_currency;
  const [selectedCompanyId, setSelectedCompanyId] = useState<number | null>(null);
  const [isCreatingNewCompany, setIsCreatingNewCompany] = useState(false);
  const [companyForm, setCompanyForm] = useState<CompanyPayload>(emptyCompanyForm);
  const [documentForm, setDocumentForm] = useState<CompanyDocumentPayload>(emptyDocumentForm);
  const [documentFile, setDocumentFile] = useState<File | null>(null);
  const [companyMessage, setCompanyMessage] = useState<string | null>(null);
  const [documentMessage, setDocumentMessage] = useState<string | null>(null);
  const [nightlyRateAmount, setNightlyRateAmount] = useState("");
  const [nightlyRateEffectiveFrom, setNightlyRateEffectiveFrom] = useState("");
  const [nightlyRateMessage, setNightlyRateMessage] = useState<string | null>(null);

  const companiesQuery = useCompanies();
  const companies = useMemo(() => companiesQuery.data ?? [], [companiesQuery.data]);
  const selectedCompany = useMemo(
    () => isCreatingNewCompany ? null : companies.find((company) => company.id === selectedCompanyId) ?? companies[0] ?? null,
    [companies, selectedCompanyId, isCreatingNewCompany]
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
    payment_deferred: Boolean(companyForm.payment_deferred),
    deferred_days: Number(companyForm.deferred_days ?? 0),
    requires_voucher: Boolean(companyForm.requires_voucher),
    requires_signature: Boolean(companyForm.requires_signature),
    notes: companyForm.notes?.trim() || null
  });

  const handleCompanySubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setCompanyMessage(null);
    if (!canManageCompanies) return;
    try {
      const payload = cleanCompanyPayload();
      const saved = selectedCompanyId
        ? await companyMutations.updateMutation.mutateAsync({ companyId: selectedCompanyId, payload })
        : await companyMutations.createMutation.mutateAsync(payload);
      setSelectedCompanyId(saved.id);
      setIsCreatingNewCompany(false);
      setCompanyMessage("Empresa guardada.");
    } catch (error) {
      setCompanyMessage(error instanceof Error ? error.message : "No se pudo guardar la empresa.");
    }
  };

  const handleActiveToggle = async (company: Company) => {
    setCompanyMessage(null);
    if (!canManageCompanies) return;
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
    if (!canManageCompanies || !selectedCompany || !documentFile) return;
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
    if (!canManageCompanies) return;
    try {
      await documentMutations.updateStatusMutation.mutateAsync({ documentId, status });
      setDocumentMessage("Estado de firma actualizado.");
    } catch (error) {
      setDocumentMessage(error instanceof Error ? error.message : "No se pudo actualizar el estado.");
    }
  };

  const handleDocumentDelete = async (documentId: number) => {
    setDocumentMessage(null);
    if (!canManageCompanies) return;
    try {
      await documentMutations.deleteDocumentMutation.mutateAsync(documentId);
      setDocumentMessage("Documento eliminado.");
    } catch (error) {
      setDocumentMessage(error instanceof Error ? error.message : "No se pudo eliminar el documento.");
    }
  };

  const documents = documentsQuery.data ?? [];
  const nightlyRatesQuery = useQuery<CompanyNightlyRatesResponse>({
    queryKey: ["company-nightly-rates", session.hotelId, selectedCompany?.id],
    queryFn: () => listCompanyNightlyRates(selectedCompany!.id, session),
    enabled: Boolean(selectedCompany?.id) && hasValidSession(session),
    staleTime: 30 * 1000
  });
  const hotelToday = nightlyRatesQuery.data?.hotel_today;
  const nightlyRates = useMemo(
    () => [...(nightlyRatesQuery.data?.rates ?? [])].sort(
      (left, right) => right.effective_from.localeCompare(left.effective_from) || right.id - left.id
    ),
    [nightlyRatesQuery.data?.rates]
  );
  useEffect(() => {
    setNightlyRateAmount("");
    setNightlyRateEffectiveFrom(hotelToday ?? "");
    setNightlyRateMessage(null);
  }, [selectedCompany?.id, hotelToday]);
  const createNightlyRateMutation = useGuardedMutation({
    mutationFn: ({ companyId, effective_from, amount }: { companyId: number; effective_from: string; amount: number }) =>
      createCompanyNightlyRate(companyId, { effective_from, amount }, session),
    onSuccess: async (_savedRate, variables) => {
      await queryClient.invalidateQueries({ queryKey: ["company-nightly-rates", session.hotelId, variables.companyId] });
    }
  });
  const handleNightlyRateSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setNightlyRateMessage(null);
    if (!selectedCompany || !canManageNightlyRates) return;
    const amount = Number(nightlyRateAmount);
    if (!Number.isFinite(amount) || amount < 0) {
      setNightlyRateMessage(t("nightlyRates.invalidAmount"));
      return;
    }
    if (!hotelToday || !nightlyRateEffectiveFrom || nightlyRateEffectiveFrom < hotelToday) {
      setNightlyRateMessage(t("nightlyRates.invalidDate"));
      return;
    }
    try {
      await createNightlyRateMutation.mutateAsync({
        companyId: selectedCompany.id,
        effective_from: nightlyRateEffectiveFrom,
        amount
      });
      setNightlyRateAmount("");
      setNightlyRateMessage(t("nightlyRates.saved"));
    } catch (error) {
      setNightlyRateMessage(error instanceof Error ? error.message : t("nightlyRates.saveError"));
    }
  };
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
        {canManageCompanies ? (
          <button
            type="button"
            onClick={() => {
              resetForNewCompany();
              setIsCreatingNewCompany(true);
            }}
            className="rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            Nueva empresa
          </button>
        ) : null}
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
                      onClick={() => {
                        setIsCreatingNewCompany(false);
                        setSelectedCompanyId(company.id);
                      }}
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
              {selectedCompany && canManageCompanies ? (
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

            {!canManageCompanies ? (
              <p className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-600" role="status">
                {t("nightlyRates.readOnly")}
              </p>
            ) : null}

            <fieldset disabled={!canManageCompanies} className="contents">
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
            </fieldset>

            {companyMessage ? (
              <div className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm text-slate-700">{companyMessage}</div>
            ) : null}

            {canManageCompanies ? (
              <div className="flex justify-end">
                <button
                  type="submit"
                  disabled={companyBusy || !companyForm.legal_name.trim() || !companyForm.display_name.trim()}
                  className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                >
                  {companyBusy ? "Guardando..." : "Guardar empresa"}
                </button>
              </div>
            ) : null}
          </form>

          {selectedCompany ? (
            <section className="space-y-4 border-t border-slate-200 pt-4" data-testid="company-nightly-rate-panel">
              <div>
                <p className="text-xs uppercase tracking-wide text-slate-500">{t("nightlyRates.historyTitle")}</p>
                <h3 className="text-base font-semibold text-slate-900">{t("nightlyRates.title")}</h3>
                <p className="mt-1 text-sm text-slate-600">{t("nightlyRates.description")}</p>
                <p className="mt-1 text-xs text-slate-500">
                  {currencyCode
                    ? t("nightlyRates.currency", { currency: currencyCode.toUpperCase() })
                    : t("nightlyRates.currencyUnavailable")}
                </p>
              </div>

              {canManageNightlyRates ? (
                <form className="grid gap-3 rounded-lg border border-slate-200 bg-slate-50 p-4 sm:grid-cols-[minmax(0,1fr)_minmax(0,1fr)_auto] sm:items-end" onSubmit={handleNightlyRateSubmit}>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-700">{t("nightlyRates.effectiveFrom")}</span>
                    <input
                      type="date"
                      min={hotelToday ?? ""}
                      required
                      value={nightlyRateEffectiveFrom}
                      onChange={(event) => setNightlyRateEffectiveFrom(event.target.value)}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
                      data-testid="company-nightly-rate-effective-date"
                    />
                  </label>
                  <label className="space-y-1 text-sm">
                    <span className="text-slate-700">{t("nightlyRates.amount")}</span>
                    <input
                      type="number"
                      min="0"
                      step="0.01"
                      required
                      value={nightlyRateAmount}
                      onChange={(event) => setNightlyRateAmount(event.target.value)}
                      className="w-full rounded-lg border border-slate-300 bg-white px-3 py-2"
                      data-testid="company-nightly-rate-amount"
                    />
                    <span className="block text-xs text-slate-500">{t("nightlyRates.zeroAmountHint")}</span>
                  </label>
                  <button
                    type="submit"
                    disabled={!hotelToday || createNightlyRateMutation.isPending || !nightlyRateAmount || !nightlyRateEffectiveFrom || nightlyRateEffectiveFrom < hotelToday}
                    className="rounded-lg border border-brand-200 bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:opacity-60"
                    data-testid="company-nightly-rate-submit"
                  >
                    {createNightlyRateMutation.isPending ? t("nightlyRates.saving") : t("nightlyRates.save")}
                  </button>
                </form>
              ) : (
                <p className="rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-sm text-amber-900" role="status">
                  {canManageCompanies ? t("nightlyRates.ratePermissionMissing") : t("nightlyRates.readOnly")}
                </p>
              )}

              {nightlyRateMessage ? (
                <p
                  className={`rounded-lg border px-3 py-2 text-sm ${createNightlyRateMutation.isError ? "border-rose-200 bg-rose-50 text-rose-800" : "border-emerald-200 bg-emerald-50 text-emerald-800"}`}
                  role={createNightlyRateMutation.isError ? "alert" : "status"}
                  aria-live="polite"
                >
                  {nightlyRateMessage}
                </p>
              ) : null}

              <div aria-live="polite">
                {nightlyRatesQuery.isLoading ? (
                  <p className="text-sm text-slate-500" role="status">{t("nightlyRates.loading")}</p>
                ) : nightlyRatesQuery.isError ? (
                  <div className="flex flex-col gap-2 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 sm:flex-row sm:items-center sm:justify-between" role="alert">
                    <span>{t("nightlyRates.historyLoadError")}</span>
                    <button
                      type="button"
                      onClick={() => void nightlyRatesQuery.refetch()}
                      className="self-start rounded-md border border-rose-300 bg-white px-3 py-1.5 font-semibold text-rose-800 hover:bg-rose-100 sm:self-auto"
                    >
                      {t("nightlyRates.retry")}
                    </button>
                  </div>
                ) : nightlyRates.length === 0 ? (
                  <p className="rounded-lg border border-dashed border-slate-300 px-3 py-4 text-sm text-slate-500">{t("nightlyRates.historyEmpty")}</p>
                ) : (
                  <ol className="divide-y divide-slate-200 rounded-lg border border-slate-200" data-testid="company-nightly-rate-history">
                    {nightlyRates.map((rate) => (
                      <li key={rate.id} className="flex flex-col gap-1 px-3 py-3 sm:flex-row sm:items-center sm:justify-between" data-testid="company-nightly-rate-row">
                        <div>
                          <p className="text-sm font-medium text-slate-900">{formatRateDate(rate.effective_from, locale)}</p>
                          {Number(rate.amount) === 0 ? <p className="text-xs text-slate-500">{t("nightlyRates.zeroRate")}</p> : null}
                        </div>
                        <span className="text-sm font-semibold text-slate-900">{formatNightlyRateAmount(rate.amount, currencyCode, locale)}</span>
                      </li>
                    ))}
                  </ol>
                )}
              </div>
            </section>
          ) : null}

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
                                disabled={documentBusy || !canManageCompanies}
                                onChange={(event) => handleStatusChange(document.id, event.target.value as CompanyDocumentStatus)}
                                className="rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-800"
                              >
                                {signatureStatuses.map((status) => (
                                  <option key={status} value={status}>
                                    {companyDocumentStatusLabel[status]}
                                  </option>
                                ))}
                              </select>
                              {canManageCompanies ? (
                                <button
                                  type="button"
                                  disabled={documentBusy}
                                  onClick={() => handleDocumentDelete(document.id)}
                                  className="rounded-lg border border-rose-200 bg-white px-3 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-60"
                                >
                                  Eliminar
                                </button>
                              ) : null}
                            </div>
                          </div>
                        </div>
                      ))}
                    </div>
                  )}
                </div>

                {canManageCompanies ? <form className="grid gap-4 md:grid-cols-2" onSubmit={handleDocumentSubmit}>
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
                </form> : null}
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
