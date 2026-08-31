import { useState } from "react";

import {
  type Promotion,
  type PromotionBenefitType,
  type PromotionConditions,
  type PromotionCreatePayload,
  type PromotionScope,
  type PromotionSimulateResult
} from "../../api/promotions";
import { ApiError, hasValidSession } from "../../api/client";
import { useCompanies } from "../../hooks/useCompanies";
import { usePromotionMutations, usePromotions, useSimulatePromotion } from "../../hooks/usePromotions";
import { useRooms } from "../../hooks/useRooms";
import { useSession } from "../../state/session";
import { formatMoney } from "../../utils/currency";

const WEEKDAY_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "mon", label: "Lun" },
  { value: "tue", label: "Mar" },
  { value: "wed", label: "Mié" },
  { value: "thu", label: "Jue" },
  { value: "fri", label: "Vie" },
  { value: "sat", label: "Sáb" },
  { value: "sun", label: "Dom" }
];

// Matches app.services.reservation_service._PRICING_PAYMENT_METHODS -- the
// canonical values that actually reach the pricing/promotion pipeline.
const PAYMENT_METHOD_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "cash", label: "Efectivo" },
  { value: "transfer", label: "Transferencia" },
  { value: "mercadopago", label: "Mercado Pago" },
  { value: "paypal", label: "PayPal" },
  { value: "credit_card", label: "Tarjeta de crédito" }
];

// Mirrors app.models.guest.GuestTagTypeEnum (see also GuestsPage.tsx TAG_OPTIONS).
const GUEST_TAG_OPTIONS: Array<{ value: string; label: string }> = [
  { value: "prohibido_alojar", label: "Prohibido alojar" },
  { value: "requiere_deposito", label: "Requiere depósito" },
  { value: "no_pago", label: "No pagó" },
  { value: "conflictivo", label: "Conflictivo" },
  { value: "robo", label: "Robo" },
  { value: "robo_cosas", label: "Rompió cosas" },
  { value: "vip", label: "VIP" },
  { value: "alergias", label: "Alergias" },
  { value: "otro", label: "Otro" }
];

type PromotionFormState = {
  code: string;
  name: string;
  description: string;
  benefit_type: PromotionBenefitType;
  benefit_value: string;
  scope: PromotionScope;
  from_night_number: string;
  priority: string;
  stackable: boolean;
  booking_from: string;
  booking_to: string;
  stay_from: string;
  stay_to: string;
  min_nights: string;
  max_nights: string;
  weekdays: string[];
  category_id: string;
  room_id: string;
  sales_channel_code: string;
  guest_id: string;
  company_id: string;
  guest_tag_type: string;
  payment_currency: string;
  payment_method: string;
};

const emptyForm: PromotionFormState = {
  code: "",
  name: "",
  description: "",
  benefit_type: "percentage",
  benefit_value: "",
  scope: "full_stay",
  from_night_number: "",
  priority: "0",
  stackable: false,
  booking_from: "",
  booking_to: "",
  stay_from: "",
  stay_to: "",
  min_nights: "",
  max_nights: "",
  weekdays: [],
  category_id: "",
  room_id: "",
  sales_channel_code: "",
  guest_id: "",
  company_id: "",
  guest_tag_type: "",
  payment_currency: "",
  payment_method: ""
};

const formFromPromotion = (promo: Promotion): PromotionFormState => ({
  code: promo.code,
  name: promo.name,
  description: promo.description ?? "",
  benefit_type: promo.benefit_type,
  benefit_value: String(promo.benefit_value),
  scope: promo.scope,
  from_night_number: promo.from_night_number != null ? String(promo.from_night_number) : "",
  priority: String(promo.priority),
  stackable: promo.stackable,
  booking_from: promo.conditions.booking_from ?? "",
  booking_to: promo.conditions.booking_to ?? "",
  stay_from: promo.conditions.stay_from ?? "",
  stay_to: promo.conditions.stay_to ?? "",
  min_nights: promo.conditions.min_nights != null ? String(promo.conditions.min_nights) : "",
  max_nights: promo.conditions.max_nights != null ? String(promo.conditions.max_nights) : "",
  weekdays: promo.conditions.weekdays ?? [],
  category_id: promo.conditions.category_id != null ? String(promo.conditions.category_id) : "",
  room_id: promo.conditions.room_id != null ? String(promo.conditions.room_id) : "",
  sales_channel_code: promo.conditions.sales_channel_code ?? "",
  guest_id: promo.conditions.guest_id != null ? String(promo.conditions.guest_id) : "",
  company_id: promo.conditions.company_id != null ? String(promo.conditions.company_id) : "",
  guest_tag_type: promo.conditions.guest_tag_type ?? "",
  payment_currency: promo.conditions.payment_currency ?? "",
  payment_method: promo.conditions.payment_method ?? ""
});

const toIntOrNull = (value: string): number | null => {
  const trimmed = value.trim();
  if (trimmed === "") return null;
  const parsed = Number.parseInt(trimmed, 10);
  return Number.isFinite(parsed) ? parsed : null;
};

const buildConditions = (form: PromotionFormState): PromotionConditions => ({
  booking_from: form.booking_from || null,
  booking_to: form.booking_to || null,
  stay_from: form.stay_from || null,
  stay_to: form.stay_to || null,
  min_nights: toIntOrNull(form.min_nights),
  max_nights: toIntOrNull(form.max_nights),
  weekdays: form.weekdays.length ? form.weekdays : null,
  category_id: toIntOrNull(form.category_id),
  room_id: toIntOrNull(form.room_id),
  sales_channel_code: form.sales_channel_code.trim() || null,
  guest_id: toIntOrNull(form.guest_id),
  company_id: toIntOrNull(form.company_id),
  guest_tag_type: form.guest_tag_type || null,
  payment_currency: form.payment_currency.trim() ? form.payment_currency.trim().toUpperCase() : null,
  payment_method: form.payment_method || null
});

const inputClass =
  "mt-1 w-full min-h-11 rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-900 shadow-sm outline-none focus:border-blue-300 focus:ring-2 focus:ring-blue-100";
const labelClass = "text-xs font-semibold text-slate-600";
const buttonPrimary =
  "min-h-11 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60";
const buttonSecondary =
  "min-h-11 rounded-lg border border-slate-200 bg-white px-4 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50 disabled:opacity-60";

function benefitSummary(promo: Pick<Promotion, "benefit_type" | "benefit_value">) {
  return promo.benefit_type === "percentage" ? `${promo.benefit_value}%` : formatMoney(promo.benefit_value);
}

function scopeSummary(promo: Pick<Promotion, "scope" | "from_night_number">) {
  return promo.scope === "full_stay" ? "Toda la estadía" : `Desde la noche ${promo.from_night_number ?? "?"}`;
}

function conditionChips(conditions: PromotionConditions): string[] {
  const chips: string[] = [];
  if (conditions.booking_from || conditions.booking_to) {
    chips.push(`Reserva: ${conditions.booking_from ?? "…"} → ${conditions.booking_to ?? "…"}`);
  }
  if (conditions.stay_from || conditions.stay_to) {
    chips.push(`Estadía: ${conditions.stay_from ?? "…"} → ${conditions.stay_to ?? "…"}`);
  }
  if (conditions.min_nights || conditions.max_nights) {
    chips.push(`Noches: ${conditions.min_nights ?? "1"}–${conditions.max_nights ?? "∞"}`);
  }
  if (conditions.weekdays?.length) chips.push(`Días: ${conditions.weekdays.join(", ")}`);
  if (conditions.category_id) chips.push(`Categoría #${conditions.category_id}`);
  if (conditions.room_id) chips.push(`Habitación #${conditions.room_id}`);
  if (conditions.sales_channel_code) chips.push(`Canal: ${conditions.sales_channel_code}`);
  if (conditions.guest_id) chips.push(`Huésped #${conditions.guest_id}`);
  if (conditions.company_id) chips.push(`Empresa #${conditions.company_id}`);
  if (conditions.guest_tag_type) chips.push(`Tag: ${GUEST_TAG_OPTIONS.find((t) => t.value === conditions.guest_tag_type)?.label ?? conditions.guest_tag_type}`);
  if (conditions.payment_currency) chips.push(`Moneda: ${conditions.payment_currency}`);
  if (conditions.payment_method) chips.push(`Pago: ${PAYMENT_METHOD_OPTIONS.find((m) => m.value === conditions.payment_method)?.label ?? conditions.payment_method}`);
  return chips;
}

export function PromotionsPage() {
  const { session } = useSession();
  const [includeInactive, setIncludeInactive] = useState(false);
  const promotionsQuery = usePromotions(includeInactive);
  const { createMutation, updateMutation, deactivateMutation, reactivateMutation } = usePromotionMutations();
  const { categoriesQuery, roomsQuery } = useRooms();
  const companiesQuery = useCompanies();

  const [showForm, setShowForm] = useState(false);
  const [editingId, setEditingId] = useState<number | null>(null);
  const [form, setForm] = useState<PromotionFormState>(emptyForm);
  const [formError, setFormError] = useState<string | null>(null);

  const startCreate = () => {
    setEditingId(null);
    setForm(emptyForm);
    setFormError(null);
    setShowForm(true);
  };

  const startEdit = (promo: Promotion) => {
    setEditingId(promo.id);
    setForm(formFromPromotion(promo));
    setFormError(null);
    setShowForm(true);
  };

  const toggleWeekday = (value: string) => {
    setForm((prev) => ({
      ...prev,
      weekdays: prev.weekdays.includes(value) ? prev.weekdays.filter((w) => w !== value) : [...prev.weekdays, value]
    }));
  };

  const showMutationError = (err: unknown) =>
    setFormError(err instanceof ApiError ? err.message : "No se pudo guardar la promoción.");

  const handleSubmit = async (event: React.FormEvent) => {
    event.preventDefault();
    setFormError(null);

    if (!form.name.trim() || (!editingId && !form.code.trim())) {
      setFormError("Completá código y nombre.");
      return;
    }
    const benefitValue = Number(form.benefit_value);
    if (!Number.isFinite(benefitValue) || benefitValue < 0) {
      setFormError("El valor del beneficio debe ser un número mayor o igual a 0.");
      return;
    }
    if (form.benefit_type === "percentage" && benefitValue > 100) {
      setFormError("El porcentaje no puede superar 100.");
      return;
    }
    if (form.scope === "from_night_n" && !form.from_night_number.trim()) {
      setFormError("Indicá desde qué noche aplica el beneficio.");
      return;
    }

    const conditions = buildConditions(form);
    if (editingId) {
      try {
        await updateMutation.mutateAsync({
          id: editingId,
          payload: {
            name: form.name.trim(),
            description: form.description.trim() || null,
            benefit_type: form.benefit_type,
            benefit_value: benefitValue,
            scope: form.scope,
            from_night_number: form.scope === "from_night_n" ? toIntOrNull(form.from_night_number) : null,
            priority: toIntOrNull(form.priority) ?? 0,
            stackable: form.stackable,
            conditions
          }
        });
        setShowForm(false);
        setEditingId(null);
      } catch (err: unknown) {
        showMutationError(err);
      }
      return;
    }

    const payload: PromotionCreatePayload = {
      code: form.code.trim(),
      name: form.name.trim(),
      description: form.description.trim() || null,
      benefit_type: form.benefit_type,
      benefit_value: benefitValue,
      scope: form.scope,
      from_night_number: form.scope === "from_night_n" ? toIntOrNull(form.from_night_number) : null,
      priority: toIntOrNull(form.priority) ?? 0,
      stackable: form.stackable,
      conditions
    };
    try {
      await createMutation.mutateAsync(payload);
      setShowForm(false);
      setForm(emptyForm);
    } catch (err: unknown) {
      showMutationError(err);
    }
  };

  if (!hasValidSession(session)) {
    return <p className="text-sm text-slate-600">Iniciá sesión con un hotel activo para gestionar promociones.</p>;
  }

  const promotions = promotionsQuery.data ?? [];
  const savePending = createMutation.isPending || updateMutation.isPending;

  return (
    <div className="space-y-5" data-testid="promotions-page">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Tarifas</p>
        <h1 className="text-2xl font-semibold text-slate-900">Promociones</h1>
        <p className="text-sm text-slate-600">
          Reglas de descuento sin código: condiciones tipadas, beneficio fijo o porcentual y simulador de precio antes
          de publicar.
        </p>
      </header>

      <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <label className="flex min-h-11 items-center gap-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={includeInactive}
              onChange={(e) => setIncludeInactive(e.target.checked)}
              className="h-4 w-4"
            />
            Mostrar inactivas
          </label>
          <button type="button" className={buttonPrimary} onClick={startCreate}>
            {showForm && !editingId ? "Nueva promoción (abierta)" : "Nueva promoción"}
          </button>
        </div>

        {promotionsQuery.isLoading ? (
          <p className="mt-4 text-sm text-slate-600">Cargando promociones...</p>
        ) : promotionsQuery.isError ? (
          <p className="mt-4 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">
            No se pudieron cargar las promociones: {(promotionsQuery.error as Error).message}
          </p>
        ) : promotions.length === 0 ? (
          <p className="mt-4 text-sm text-slate-500">No hay promociones creadas todavía.</p>
        ) : (
          <ul className="mt-4 space-y-3">
            {promotions.map((promo) => (
              <li key={promo.id} className="rounded-lg border border-slate-200 p-3 text-sm">
                <div className="flex flex-wrap items-start justify-between gap-2">
                  <div className="min-w-0">
                    <p className="font-semibold text-slate-900">
                      {promo.name} <span className="font-normal text-slate-500">({promo.code} · v{promo.version})</span>
                    </p>
                    <p className="mt-0.5 text-xs text-slate-600">
                      {benefitSummary(promo)} · {scopeSummary(promo)} · prioridad {promo.priority} ·{" "}
                      {promo.stackable ? "combinable" : "no combinable"}
                    </p>
                  </div>
                  <span
                    className={`shrink-0 rounded-full px-2 py-1 text-xs font-semibold ${
                      promo.is_active ? "bg-emerald-100 text-emerald-700" : "bg-slate-200 text-slate-600"
                    }`}
                  >
                    {promo.is_active ? "Activa" : "Inactiva"}
                  </span>
                </div>
                {conditionChips(promo.conditions).length > 0 ? (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {conditionChips(promo.conditions).map((chip) => (
                      <span key={chip} className="rounded-full bg-slate-100 px-2 py-0.5 text-[11px] text-slate-600">
                        {chip}
                      </span>
                    ))}
                  </div>
                ) : (
                  <p className="mt-2 text-[11px] text-slate-400">Sin condiciones: aplica a cualquier reserva.</p>
                )}
                <div className="mt-3 flex flex-wrap gap-2">
                  <button type="button" className={buttonSecondary} onClick={() => startEdit(promo)}>
                    Editar
                  </button>
                  {promo.is_active ? (
                    <button
                      type="button"
                      className="min-h-11 rounded-lg border border-rose-200 px-4 py-2 text-sm font-semibold text-rose-700 hover:bg-rose-50 disabled:opacity-60"
                      disabled={deactivateMutation.isPending}
                      onClick={() => void deactivateMutation.mutateAsync(promo.id).catch((err: unknown) => showMutationError(err))}
                    >
                      Desactivar
                    </button>
                  ) : (
                    <button
                      type="button"
                      className="min-h-11 rounded-lg border border-emerald-200 px-4 py-2 text-sm font-semibold text-emerald-700 hover:bg-emerald-50 disabled:opacity-60"
                      disabled={reactivateMutation.isPending}
                      onClick={() => void reactivateMutation.mutateAsync(promo.id).catch((err: unknown) => showMutationError(err))}
                    >
                      Reactivar
                    </button>
                  )}
                </div>
              </li>
            ))}
          </ul>
        )}
      </section>

      {showForm ? (
        <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6" data-testid="promotion-form">
          <div className="flex items-center justify-between gap-3">
            <h2 className="text-lg font-semibold text-slate-900">{editingId ? "Editar promoción" : "Nueva promoción"}</h2>
            <button type="button" className={buttonSecondary} onClick={() => setShowForm(false)}>
              Cerrar
            </button>
          </div>
          {editingId ? (
            <p className="mt-1 text-xs text-slate-500">
              Guardar crea una nueva versión; las reservas ya hechas conservan el precio con el que se cotizaron.
            </p>
          ) : null}

          <form onSubmit={handleSubmit} className="mt-4 space-y-4">
            <div className="grid gap-3 sm:grid-cols-3">
              <label className={labelClass}>
                Código
                <input
                  className={inputClass}
                  value={form.code}
                  disabled={Boolean(editingId)}
                  onChange={(e) => setForm((p) => ({ ...p, code: e.target.value }))}
                  placeholder="EJ. VERANO2026"
                />
              </label>
              <label className={`${labelClass} sm:col-span-2`}>
                Nombre
                <input
                  className={inputClass}
                  value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                  placeholder="Descuento de verano"
                />
              </label>
              <label className={`${labelClass} sm:col-span-3`}>
                Descripción (opcional)
                <textarea
                  className={inputClass}
                  rows={2}
                  value={form.description}
                  onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
                />
              </label>
            </div>

            <div className="grid gap-3 sm:grid-cols-4">
              <label className={labelClass}>
                Tipo de beneficio
                <select
                  className={inputClass}
                  value={form.benefit_type}
                  onChange={(e) => setForm((p) => ({ ...p, benefit_type: e.target.value as PromotionBenefitType }))}
                >
                  <option value="percentage">Porcentaje (%)</option>
                  <option value="fixed">Monto fijo</option>
                </select>
              </label>
              <label className={labelClass}>
                Valor
                <input
                  type="number"
                  min={0}
                  step="0.01"
                  className={inputClass}
                  value={form.benefit_value}
                  onChange={(e) => setForm((p) => ({ ...p, benefit_value: e.target.value }))}
                  placeholder={form.benefit_type === "percentage" ? "Ej. 15" : "Ej. 5000"}
                />
              </label>
              <label className={labelClass}>
                Alcance
                <select
                  className={inputClass}
                  value={form.scope}
                  onChange={(e) => setForm((p) => ({ ...p, scope: e.target.value as PromotionScope }))}
                >
                  <option value="full_stay">Toda la estadía</option>
                  <option value="from_night_n">Desde la noche N</option>
                </select>
              </label>
              <label className={labelClass}>
                Prioridad
                <input
                  type="number"
                  className={inputClass}
                  value={form.priority}
                  onChange={(e) => setForm((p) => ({ ...p, priority: e.target.value }))}
                />
              </label>
              {form.scope === "from_night_n" ? (
                <label className={labelClass}>
                  Desde noche
                  <input
                    type="number"
                    min={1}
                    className={inputClass}
                    value={form.from_night_number}
                    onChange={(e) => setForm((p) => ({ ...p, from_night_number: e.target.value }))}
                  />
                </label>
              ) : null}
              <label className="flex min-h-11 items-center gap-2 text-sm text-slate-700 sm:col-span-1">
                <input
                  type="checkbox"
                  checked={form.stackable}
                  onChange={(e) => setForm((p) => ({ ...p, stackable: e.target.checked }))}
                  className="h-4 w-4"
                />
                Combinable con otras promociones
              </label>
            </div>

            <fieldset className="rounded-lg border border-slate-200 p-3">
              <legend className="px-1 text-xs font-semibold uppercase tracking-wide text-slate-500">
                Condiciones (vacío = sin restricción)
              </legend>
              <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
                <label className={labelClass}>
                  Reserva desde
                  <input type="date" className={inputClass} value={form.booking_from} onChange={(e) => setForm((p) => ({ ...p, booking_from: e.target.value }))} />
                </label>
                <label className={labelClass}>
                  Reserva hasta
                  <input type="date" className={inputClass} value={form.booking_to} onChange={(e) => setForm((p) => ({ ...p, booking_to: e.target.value }))} />
                </label>
                <label className={labelClass}>
                  Estadía desde
                  <input type="date" className={inputClass} value={form.stay_from} onChange={(e) => setForm((p) => ({ ...p, stay_from: e.target.value }))} />
                </label>
                <label className={labelClass}>
                  Estadía hasta
                  <input type="date" className={inputClass} value={form.stay_to} onChange={(e) => setForm((p) => ({ ...p, stay_to: e.target.value }))} />
                </label>
                <label className={labelClass}>
                  Noches mínimas
                  <input type="number" min={1} className={inputClass} value={form.min_nights} onChange={(e) => setForm((p) => ({ ...p, min_nights: e.target.value }))} />
                </label>
                <label className={labelClass}>
                  Noches máximas
                  <input type="number" min={1} className={inputClass} value={form.max_nights} onChange={(e) => setForm((p) => ({ ...p, max_nights: e.target.value }))} />
                </label>
                <label className={labelClass}>
                  Categoría
                  <select className={inputClass} value={form.category_id} onChange={(e) => setForm((p) => ({ ...p, category_id: e.target.value }))}>
                    <option value="">Cualquiera</option>
                    {(categoriesQuery.data ?? []).map((c) => (
                      <option key={c.id} value={c.id}>{c.name}</option>
                    ))}
                  </select>
                </label>
                <label className={labelClass}>
                  Habitación
                  <select className={inputClass} value={form.room_id} onChange={(e) => setForm((p) => ({ ...p, room_id: e.target.value }))}>
                    <option value="">Cualquiera</option>
                    {(roomsQuery.data ?? []).map((r) => (
                      <option key={r.id} value={r.id}>Hab {r.room_number}</option>
                    ))}
                  </select>
                </label>
                <label className={labelClass}>
                  Canal de venta
                  <input className={inputClass} value={form.sales_channel_code} onChange={(e) => setForm((p) => ({ ...p, sales_channel_code: e.target.value }))} placeholder="direct, booking, expedia..." />
                </label>
                <label className={labelClass}>
                  Huésped (ID, opcional)
                  <input type="number" min={1} className={inputClass} value={form.guest_id} onChange={(e) => setForm((p) => ({ ...p, guest_id: e.target.value }))} />
                </label>
                <label className={labelClass}>
                  Empresa
                  <select className={inputClass} value={form.company_id} onChange={(e) => setForm((p) => ({ ...p, company_id: e.target.value }))}>
                    <option value="">Cualquiera</option>
                    {(companiesQuery.data ?? []).map((c) => (
                      <option key={c.id} value={c.id}>{c.display_name}</option>
                    ))}
                  </select>
                </label>
                <label className={labelClass}>
                  Tag de huésped
                  <select className={inputClass} value={form.guest_tag_type} onChange={(e) => setForm((p) => ({ ...p, guest_tag_type: e.target.value }))}>
                    <option value="">Cualquiera</option>
                    {GUEST_TAG_OPTIONS.map((t) => (
                      <option key={t.value} value={t.value}>{t.label}</option>
                    ))}
                  </select>
                </label>
                <label className={labelClass}>
                  Moneda de pago
                  <input className={inputClass} maxLength={3} value={form.payment_currency} onChange={(e) => setForm((p) => ({ ...p, payment_currency: e.target.value.toUpperCase() }))} placeholder="ARS, USD..." />
                </label>
                <label className={labelClass}>
                  Medio de pago
                  <select className={inputClass} value={form.payment_method} onChange={(e) => setForm((p) => ({ ...p, payment_method: e.target.value }))}>
                    <option value="">Cualquiera</option>
                    {PAYMENT_METHOD_OPTIONS.map((m) => (
                      <option key={m.value} value={m.value}>{m.label}</option>
                    ))}
                  </select>
                </label>
              </div>
              <div className="mt-3">
                <p className={labelClass}>Días de la semana</p>
                <div className="mt-1 flex flex-wrap gap-2">
                  {WEEKDAY_OPTIONS.map((day) => {
                    const active = form.weekdays.includes(day.value);
                    return (
                      <button
                        key={day.value}
                        type="button"
                        aria-pressed={active}
                        onClick={() => toggleWeekday(day.value)}
                        className={`min-h-11 min-w-11 rounded-lg px-3 text-sm font-semibold ${
                          active ? "bg-slate-900 text-white" : "border border-slate-200 bg-white text-slate-700 hover:bg-slate-100"
                        }`}
                      >
                        {day.label}
                      </button>
                    );
                  })}
                </div>
              </div>
            </fieldset>

            {formError ? (
              <p role="alert" className="rounded-lg bg-rose-50 p-3 text-sm text-rose-700">
                {formError}
              </p>
            ) : null}

            <div className="flex flex-wrap justify-end gap-2">
              <button type="button" className={buttonSecondary} onClick={() => setShowForm(false)}>
                Cancelar
              </button>
              <button type="submit" className={buttonPrimary} disabled={savePending}>
                {savePending ? "Guardando..." : editingId ? "Guardar nueva versión" : "Crear promoción"}
              </button>
            </div>
          </form>
        </section>
      ) : null}

      <PromotionSimulator />
    </div>
  );
}

function PromotionSimulator() {
  const { categoriesQuery } = useRooms();
  const simulateMutation = useSimulatePromotion();
  const [categoryId, setCategoryId] = useState("");
  const [checkIn, setCheckIn] = useState("");
  const [checkOut, setCheckOut] = useState("");
  const [paymentMethod, setPaymentMethod] = useState("");
  const [targetCurrency, setTargetCurrency] = useState("");
  const [salesChannel, setSalesChannel] = useState("");
  const [guestId, setGuestId] = useState("");
  const [companyId, setCompanyId] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<PromotionSimulateResult | null>(null);

  const canSimulate = Boolean(categoryId && checkIn && checkOut);

  const handleSimulate = async (event: React.FormEvent) => {
    event.preventDefault();
    setError(null);
    if (!canSimulate) {
      setError("Elegí categoría y fechas de entrada/salida.");
      return;
    }
    try {
      const simulation = await simulateMutation.mutateAsync({
        category_id: Number(categoryId),
        check_in_date: checkIn,
        check_out_date: checkOut,
        payment_method: paymentMethod || null,
        target_currency: targetCurrency.trim() ? targetCurrency.trim().toUpperCase() : null,
        sales_channel_code: salesChannel.trim() || null,
        guest_id: toIntOrNull(guestId),
        company_id: toIntOrNull(companyId)
      });
      setResult(simulation);
    } catch (err: unknown) {
      setError(err instanceof ApiError ? err.message : "No se pudo simular la cotización.");
    }
  };

  const currency = result?.output_currency ?? "ARS";

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-6" data-testid="promotion-simulator">
      <h2 className="text-lg font-semibold text-slate-900">Simulador de precio</h2>
      <p className="mt-1 text-sm text-slate-600">
        Probá una reserva hipotética y mirá qué promociones aplicarían y el desglose final, sin crear nada.
      </p>

      <form onSubmit={handleSimulate} className="mt-4 grid gap-3 sm:grid-cols-3 lg:grid-cols-6">
        <label className={labelClass}>
          Categoría
          <select className={inputClass} value={categoryId} onChange={(e) => setCategoryId(e.target.value)}>
            <option value="">Elegir…</option>
            {(categoriesQuery.data ?? []).map((c) => (
              <option key={c.id} value={c.id}>{c.name}</option>
            ))}
          </select>
        </label>
        <label className={labelClass}>
          Check-in
          <input type="date" className={inputClass} value={checkIn} onChange={(e) => setCheckIn(e.target.value)} />
        </label>
        <label className={labelClass}>
          Check-out
          <input type="date" className={inputClass} value={checkOut} onChange={(e) => setCheckOut(e.target.value)} />
        </label>
        <label className={labelClass}>
          Medio de pago
          <select className={inputClass} value={paymentMethod} onChange={(e) => setPaymentMethod(e.target.value)}>
            <option value="">Sin especificar</option>
            {PAYMENT_METHOD_OPTIONS.map((m) => (
              <option key={m.value} value={m.value}>{m.label}</option>
            ))}
          </select>
        </label>
        <label className={labelClass}>
          Moneda destino
          <input className={inputClass} maxLength={3} value={targetCurrency} onChange={(e) => setTargetCurrency(e.target.value.toUpperCase())} placeholder="Moneda del hotel" />
        </label>
        <label className={labelClass}>
          Canal
          <input className={inputClass} value={salesChannel} onChange={(e) => setSalesChannel(e.target.value)} placeholder="direct, booking..." />
        </label>
        <label className={labelClass}>
          Huésped (ID)
          <input type="number" min={1} className={inputClass} value={guestId} onChange={(e) => setGuestId(e.target.value)} />
        </label>
        <label className={labelClass}>
          Empresa (ID)
          <input type="number" min={1} className={inputClass} value={companyId} onChange={(e) => setCompanyId(e.target.value)} />
        </label>
        <div className="flex items-end">
          <button type="submit" className={`${buttonPrimary} w-full`} disabled={simulateMutation.isPending}>
            {simulateMutation.isPending ? "Simulando..." : "Simular"}
          </button>
        </div>
      </form>

      {error ? (
        <p role="alert" className="mt-3 rounded-lg bg-rose-50 p-3 text-sm text-rose-700">
          {error}
        </p>
      ) : null}

      {result ? (
        <div className="mt-4 space-y-3" data-testid="promotion-simulator-result">
          <div className="overflow-x-auto rounded-lg border border-slate-200">
            <table className="min-w-full text-left text-xs">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="px-3 py-2 font-semibold">Noche</th>
                  <th className="px-3 py-2 font-semibold">Base</th>
                  <th className="px-3 py-2 font-semibold">Promociones</th>
                  <th className="px-3 py-2 text-right font-semibold">Neto</th>
                </tr>
              </thead>
              <tbody>
                {result.per_night.map((night) => (
                  <tr key={night.date} className="border-t border-slate-100">
                    <td className="px-3 py-2 text-slate-700">{night.date}</td>
                    <td className="px-3 py-2 text-slate-600">{formatMoney(Number(night.base_amount), result.base_currency)}</td>
                    <td className="px-3 py-2 text-slate-600">
                      {night.promotions_applied.length
                        ? night.promotions_applied.map((p) => `${p.code} (-${formatMoney(Number(p.amount_deducted), result.base_currency)})`).join(", ")
                        : "—"}
                    </td>
                    <td className="px-3 py-2 text-right font-semibold text-slate-900">
                      {formatMoney(Number(night.post_promotion_amount), result.base_currency)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>

          <div className="grid gap-2 sm:grid-cols-3 lg:grid-cols-6">
            <div className="rounded-lg border border-blue-100 bg-blue-50/50 px-3 py-2 text-sm">
              <p className="text-xs text-slate-500">Subtotal</p>
              <p className="font-semibold text-slate-900">{formatMoney(Number(result.subtotal_amount), result.base_currency)}</p>
            </div>
            <div className="rounded-lg border border-blue-100 bg-blue-50/50 px-3 py-2 text-sm">
              <p className="text-xs text-slate-500">Impuestos</p>
              <p className="font-semibold text-slate-900">{formatMoney(Number(result.tax_amount), result.base_currency)}</p>
            </div>
            <div className="rounded-lg border border-blue-100 bg-blue-50/50 px-3 py-2 text-sm">
              <p className="text-xs text-slate-500">Cargos</p>
              <p className="font-semibold text-slate-900">{formatMoney(Number(result.fee_amount), result.base_currency)}</p>
            </div>
            <div className="rounded-lg border border-blue-100 bg-blue-50/50 px-3 py-2 text-sm">
              <p className="text-xs text-slate-500">Tipo de cambio</p>
              <p className="font-semibold text-slate-900">{result.fx_rate_snapshot ? `${result.fx_rate_snapshot} (${result.base_currency}→${result.output_currency})` : "No aplica"}</p>
            </div>
            <div className="rounded-lg border border-emerald-200 bg-emerald-50 px-3 py-2 text-sm">
              <p className="text-xs text-slate-500">Total reserva</p>
              <p className="font-semibold text-emerald-800">{formatMoney(Number(result.booking_total), currency)}</p>
            </div>
            <div className="rounded-lg border border-violet-200 bg-violet-50 px-3 py-2 text-sm">
              <p className="text-xs text-slate-500">
                Total con ajuste de pago{result.payment_adjustment ? ` (${result.payment_adjustment.payment_method})` : ""}
              </p>
              <p className="font-semibold text-violet-800">{formatMoney(Number(result.final_total_with_payment_adjustment), currency)}</p>
            </div>
          </div>

          {result.promotions_applied.length === 0 ? (
            <p className="text-xs text-slate-500">Ninguna promoción activa aplica a esta reserva hipotética.</p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}

export default PromotionsPage;
