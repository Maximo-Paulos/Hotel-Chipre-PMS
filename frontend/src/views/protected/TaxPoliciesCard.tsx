import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import {
  createTaxPolicy,
  listTaxPolicies,
  updateTaxPolicy,
  type TaxPolicy,
  type TaxPolicyWrite,
  type TaxRule
} from "../../api/commercial";
import { useSession } from "../../state/session";
import { hasValidSession } from "../../api/client";
import { useEffectivePermissions } from "../../hooks/usePermissions";
import { useGuardedMutation } from "../../hooks/useGuardedMutation";
import { invalidateQueriesInBackground, refreshAfterMutation } from "../../api/queryInvalidation";

type RuleDraft = Omit<TaxRule, "id">;

const emptyRule = (): RuleDraft => ({
  channel_code: null,
  guest_scope: "all",
  tax_code: "",
  tax_name: "",
  tax_type: "percentage",
  amount: 0,
  currency_code: null,
  priority: 100,
  applies_when_json: null,
  is_active: true
});

const emptyPolicy = (): TaxPolicyWrite => ({
  code: "DEFAULT",
  name: "Política impositiva del hotel",
  taxes_included: true,
  apply_vat_by_default: false,
  vat_rate: 0,
  foreign_guest_tax_exempt: false,
  is_active: true,
  metadata_json: null,
  rules: []
});

function withoutRuleId(rule: TaxRule): RuleDraft {
  return {
    channel_code: rule.channel_code,
    guest_scope: rule.guest_scope,
    tax_code: rule.tax_code,
    tax_name: rule.tax_name,
    tax_type: rule.tax_type,
    amount: rule.amount,
    currency_code: rule.currency_code,
    priority: rule.priority,
    applies_when_json: rule.applies_when_json,
    is_active: rule.is_active
  };
}

function ruleIsPerNight(rule: RuleDraft): boolean {
  if (!rule.applies_when_json) return false;
  try {
    return Boolean((JSON.parse(rule.applies_when_json) as { per_night?: unknown }).per_night);
  } catch {
    return false;
  }
}

export function TaxPoliciesCard() {
  const { session } = useSession();
  const { hasPermission, permissionsKnown } = useEffectivePermissions();
  const queryClient = useQueryClient();
  const canManage = permissionsKnown && hasPermission("commercial:manage");
  const canRead = permissionsKnown && hasPermission("reports:financial:view");
  const canLoad = canManage || canRead;
  const policiesQuery = useQuery({
    queryKey: ["tax-policies", session.hotelId],
    enabled: hasValidSession(session) && canLoad,
    queryFn: () => listTaxPolicies(session),
    staleTime: 5 * 60 * 1000
  });
  const policyToEdit = useMemo(
    () => (policiesQuery.data ?? []).find((policy) => policy.is_active) ?? policiesQuery.data?.[0] ?? null,
    [policiesQuery.data]
  );
  const [draft, setDraft] = useState<TaxPolicyWrite>(emptyPolicy);
  const [vatRateInput, setVatRateInput] = useState("0");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (!policyToEdit) {
      setDraft(emptyPolicy());
      setVatRateInput("0");
      return;
    }
    setDraft({
      code: policyToEdit.code,
      name: policyToEdit.name,
      taxes_included: policyToEdit.taxes_included,
      apply_vat_by_default: policyToEdit.apply_vat_by_default,
      vat_rate: policyToEdit.vat_rate ?? 0,
      foreign_guest_tax_exempt: policyToEdit.foreign_guest_tax_exempt,
      is_active: true,
      metadata_json: policyToEdit.metadata_json ?? null,
      rules: policyToEdit.rules.map(withoutRuleId)
    });
    setVatRateInput(String(policyToEdit.vat_rate ?? 0));
  }, [policyToEdit]);

  const saveMutation = useGuardedMutation({
    mutationFn: (payload: TaxPolicyWrite) =>
      policyToEdit
        ? updateTaxPolicy(policyToEdit.id, payload, session)
        : createTaxPolicy(payload, session),
    onSuccess: async () => {
      await refreshAfterMutation(queryClient, session.hotelId, ["settings", "reservations"]);
      invalidateQueriesInBackground(queryClient, {
        queryKey: ["tax-policies", session.hotelId]
      });
      setSaveError(null);
      setSaved(true);
    }
  });

  const updateRule = (index: number, patch: Partial<RuleDraft>) => {
    setDraft((current) => ({
      ...current,
      rules: current.rules.map((rule, ruleIndex) => ruleIndex === index ? { ...rule, ...patch } : rule)
    }));
  };

  const handleSave = async () => {
    setSaveError(null);
    setSaved(false);
    if (!draft.code.trim() || !draft.name.trim()) {
      setSaveError("Completá el código y el nombre de la política.");
      return;
    }
    const parsedVatRate = Number(vatRateInput);
    if (draft.apply_vat_by_default && (!Number.isFinite(parsedVatRate) || parsedVatRate < 0 || parsedVatRate > 100)) {
      setSaveError("Ingresá una tasa de IVA entre 0 y 100. Para indicar que no aplica, usá 0%.");
      return;
    }
    if (draft.rules.some((rule) => !rule.tax_code.trim() || !rule.tax_name.trim() || !Number.isFinite(rule.amount) || rule.amount < 0)) {
      setSaveError("Cada regla debe tener código, nombre e importe válidos.");
      return;
    }
    try {
      await saveMutation.mutateAsync({
        ...draft,
        code: draft.code.trim().toUpperCase(),
        name: draft.name.trim(),
        vat_rate: draft.apply_vat_by_default ? parsedVatRate : 0,
        is_active: true,
        rules: draft.rules.map((rule) => ({
          ...rule,
          tax_code: rule.tax_code.trim().toUpperCase(),
          tax_name: rule.tax_name.trim(),
          channel_code: rule.channel_code?.trim() || null,
          currency_code: rule.tax_type === "fixed" ? rule.currency_code?.trim().toUpperCase() || null : null,
          applies_when_json: rule.applies_when_json || null
        }))
      });
    } catch (error) {
      setSaveError(error instanceof Error ? error.message : "No se pudo guardar la política impositiva.");
    }
  };

  if (!canLoad) return null;

  const activePolicies = (policiesQuery.data ?? []).filter((policy) => policy.is_active);
  const currentPolicy: TaxPolicy | null = policyToEdit;

  return (
    <section className="space-y-4 rounded-lg border border-slate-200 bg-white p-4" aria-labelledby="tax-policy-heading">
      <div>
        <h3 id="tax-policy-heading" className="text-base font-semibold text-slate-900">Política impositiva del hotel</h3>
        <p className="mt-1 text-sm text-slate-600">
          Cada hotel debe dejar definida una política activa antes de cotizar o crear reservas. Si no cobra impuestos, guardá una política explícita de 0%; la ausencia de configuración bloquea las cotizaciones.
        </p>
      </div>

      {policiesQuery.isLoading ? (
        <p role="status" className="text-sm text-slate-600">Cargando política impositiva…</p>
      ) : policiesQuery.isError ? (
        <p role="alert" className="text-sm text-rose-700">No se pudo consultar la política impositiva.</p>
      ) : !currentPolicy ? (
        <p className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          Todavía no hay una política activa. El owner o co-owner debe completar y guardar la configuración para habilitar cotizaciones y nuevas reservas.
        </p>
      ) : activePolicies.length > 1 ? (
        <p className="rounded-lg border border-amber-300 bg-amber-50 p-3 text-sm text-amber-900">
          Hay más de una política activa. Las cotizaciones sin selección usan la política activa con el ID más bajo; revisá las políticas antes de operar.
        </p>
      ) : null}

      {!canManage ? (
        currentPolicy && (
          <p className="text-sm text-slate-700">
            Activa: <strong>{currentPolicy.name}</strong>{" · "}
            {currentPolicy.apply_vat_by_default ? `IVA ${currentPolicy.vat_rate ?? 0}%` : "sin IVA por defecto"}
            {currentPolicy.rules.length > 0 ? ` · ${currentPolicy.rules.length} reglas adicionales` : ""}
          </p>
        )
      ) : (
        <div className="space-y-4">
          <div className="grid gap-3 sm:grid-cols-2">
            <label className="text-sm font-semibold text-slate-700">
              Código
              <input
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
                value={draft.code}
                onChange={(event) => setDraft((current) => ({ ...current, code: event.target.value }))}
                maxLength={50}
              />
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Nombre
              <input
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2"
                value={draft.name}
                onChange={(event) => setDraft((current) => ({ ...current, name: event.target.value }))}
                maxLength={150}
              />
            </label>
          </div>

          <div className="grid gap-3 sm:grid-cols-2">
            <label className="flex items-start gap-2 rounded-lg border border-slate-200 p-3 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={draft.apply_vat_by_default}
                onChange={(event) => setDraft((current) => ({ ...current, apply_vat_by_default: event.target.checked }))}
              />
              <span>Aplicar IVA por defecto. Desmarcalo y guardá 0% para indicar que no aplica.</span>
            </label>
            <label className="text-sm font-semibold text-slate-700">
              Tasa de IVA (%)
              <input
                type="number"
                min={0}
                max={100}
                step="0.01"
                disabled={!draft.apply_vat_by_default}
                className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 disabled:bg-slate-100"
                value={vatRateInput}
                onChange={(event) => setVatRateInput(event.target.value)}
              />
            </label>
            <label className="flex items-start gap-2 rounded-lg border border-slate-200 p-3 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={draft.taxes_included}
                onChange={(event) => setDraft((current) => ({ ...current, taxes_included: event.target.checked }))}
              />
              <span>Los precios del calendario diario ya incluyen los impuestos configurados. Cada precio de plan tarifario conserva su propia opción de inclusión.</span>
            </label>
            <label className="flex items-start gap-2 rounded-lg border border-slate-200 p-3 text-sm text-slate-700">
              <input
                type="checkbox"
                checked={draft.foreign_guest_tax_exempt}
                onChange={(event) => setDraft((current) => ({ ...current, foreign_guest_tax_exempt: event.target.checked }))}
              />
              <span>Eximir huéspedes extranjeros de las reglas impositivas.</span>
            </label>
          </div>

          <div className="space-y-3 rounded-lg border border-slate-200 bg-slate-50 p-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <div>
                <h4 className="text-sm font-semibold text-slate-800">Reglas adicionales</h4>
                <p className="text-xs text-slate-600">Cada regla queda asociada a este hotel y puede variar por canal o tipo de huésped.</p>
              </div>
              <button
                type="button"
                onClick={() => setDraft((current) => ({ ...current, rules: [...current.rules, emptyRule()] }))}
                className="rounded-lg border border-slate-300 bg-white px-3 py-2 text-xs font-semibold text-slate-700 hover:bg-slate-100"
              >
                Agregar regla
              </button>
            </div>
            {draft.rules.length === 0 ? (
              <p className="text-xs text-slate-500">No hay reglas adicionales configuradas.</p>
            ) : draft.rules.map((rule, index) => (
              <div key={`${index}-${rule.tax_code}`} className="grid gap-2 rounded-lg border border-slate-200 bg-white p-3 sm:grid-cols-2 lg:grid-cols-4">
                <label className="text-xs font-semibold text-slate-700">
                  Código
                  <input className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5" value={rule.tax_code} onChange={(event) => updateRule(index, { tax_code: event.target.value })} maxLength={50} />
                </label>
                <label className="text-xs font-semibold text-slate-700">
                  Nombre
                  <input className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5" value={rule.tax_name} onChange={(event) => updateRule(index, { tax_name: event.target.value })} maxLength={150} />
                </label>
                <label className="text-xs font-semibold text-slate-700">
                  Tipo
                  <select className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5" value={rule.tax_type} onChange={(event) => updateRule(index, { tax_type: event.target.value as RuleDraft["tax_type"] })}>
                    <option value="percentage">Porcentaje</option>
                    <option value="fixed">Monto fijo</option>
                  </select>
                </label>
                <label className="text-xs font-semibold text-slate-700">
                  Importe {rule.tax_type === "percentage" ? "(%)" : ""}
                  <input type="number" min={0} step="0.01" className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5" value={rule.amount} onChange={(event) => updateRule(index, { amount: Number(event.target.value) })} />
                </label>
                <label className="text-xs font-semibold text-slate-700">
                  Huésped
                  <select className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5" value={rule.guest_scope} onChange={(event) => updateRule(index, { guest_scope: event.target.value as RuleDraft["guest_scope"] })}>
                    <option value="all">Todos</option>
                    <option value="local">Local</option>
                    <option value="foreign">Extranjero</option>
                  </select>
                </label>
                <label className="text-xs font-semibold text-slate-700">
                  Canal (opcional)
                  <input className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5" value={rule.channel_code ?? ""} onChange={(event) => updateRule(index, { channel_code: event.target.value || null })} maxLength={50} />
                </label>
                {rule.tax_type === "fixed" && (
                  <label className="text-xs font-semibold text-slate-700">
                    Moneda (opcional; debe coincidir con la tarifa)
                    <input className="mt-1 w-full rounded border border-slate-200 px-2 py-1.5 uppercase" value={rule.currency_code ?? ""} onChange={(event) => updateRule(index, { currency_code: event.target.value || null })} maxLength={3} />
                  </label>
                )}
                <label className="flex items-center gap-2 text-xs text-slate-700">
                  <input
                    type="checkbox"
                    checked={ruleIsPerNight(rule)}
                    onChange={(event) => updateRule(index, { applies_when_json: event.target.checked ? JSON.stringify({ per_night: true }) : null })}
                  />
                  Se calcula por noche
                </label>
                <button type="button" onClick={() => setDraft((current) => ({ ...current, rules: current.rules.filter((_, ruleIndex) => ruleIndex !== index) }))} className="justify-self-start rounded-lg border border-rose-200 px-3 py-1.5 text-xs font-semibold text-rose-700 hover:bg-rose-50">
                  Quitar regla
                </button>
              </div>
            ))}
          </div>

          {saveError && <p role="alert" className="text-sm text-rose-700">{saveError}</p>}
          {saved && <p role="status" className="text-sm text-emerald-700">La política impositiva quedó guardada.</p>}
          <button
            type="button"
            onClick={() => void handleSave()}
            disabled={saveMutation.isPending}
            className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
          >
            {saveMutation.isPending ? "Guardando…" : currentPolicy ? "Guardar política" : "Crear política activa"}
          </button>
        </div>
      )}
    </section>
  );
}
