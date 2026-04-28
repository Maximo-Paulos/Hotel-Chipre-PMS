import { useEffect, useMemo, useState, type ReactNode } from "react";
import { Link, Navigate, useParams } from "react-router-dom";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import { apiFetch } from "../../../api/client";
import { useSubscriptionStatus } from "../../../hooks/useSubscription";
import { formatMoney } from "../../../utils/currency";
import { StatCard } from "../../../components/StatCard";
import { useSession } from "../../../state/session";

type AnalyticsEnvelope = {
  hotel_id: number;
  date_from?: string;
  date_to?: string;
  currency_display?: string;
  generated_at?: string;
  comparison?: Record<string, unknown>;
  data: Record<string, unknown>;
};

type AnalyticsStarterSummary = {
  hotel_id: number;
  date_from?: string;
  date_to?: string;
  data: { cards: Array<Record<string, unknown>> };
  generated_at?: string;
};

type Company = {
  id: number;
  legal_name: string;
  display_name: string;
  tax_id?: string | null;
  country_code?: string | null;
  notes?: string | null;
  is_active: boolean;
};

type RoomStateEvent = {
  id: number;
  room_id: number;
  event_type: string;
  reason_code: string;
  reason_note?: string | null;
  started_at: string;
  ended_at?: string | null;
  created_by_user_id: number;
  closed_by_user_id?: number | null;
};

type RoomStateEventCreate = {
  room_id: number;
  event_type: "out_of_service" | "maintenance" | "housekeeping_block" | "renovation";
  reason_code: "plumbing" | "electrical" | "furniture" | "deep_clean" | "inspection" | "other";
  reason_note?: string | null;
  started_at?: string | null;
};

type AnalyticsAIStatus = {
  hotel_id: number;
  analytics_ai_enabled: boolean;
  provider: string;
  runtime_healthy: boolean;
  effective_model?: string | null;
  runtime_status: string;
  fallback_reason?: string | null;
};

type AnalyticsAIChatResponse = {
  hotel_id: number;
  answer: string;
  warnings: string[];
  recommendations: string[];
  generated_at: string;
};

type ChatMessage = {
  role: "user" | "assistant";
  text: string;
  warnings?: string[];
  recommendations?: string[];
};

const planRank: Record<string, number> = { starter: 0, pro: 1, ultra: 2 };

type AnalyticsFilterState = {
  date_from: string;
  date_to: string;
  currency_display: "ARS" | "USD" | "BOTH";
  compare_previous: boolean;
  compare_yoy: boolean;
};

const analyticsFilterStorageKey = (hotelId: number | null, routeName: string) =>
  hotelId ? `analytics:filters:${hotelId}:${routeName}` : null;

const localDateIso = (date = new Date()) => {
  const year = date.getFullYear();
  const month = String(date.getMonth() + 1).padStart(2, "0");
  const day = String(date.getDate()).padStart(2, "0");
  return `${year}-${month}-${day}`;
};

const startOfCurrentLocalMonthIso = () => {
  const date = new Date();
  date.setDate(1);
  return localDateIso(date);
};

const defaultAnalyticsFilters = (): AnalyticsFilterState => ({
  date_from: startOfCurrentLocalMonthIso(),
  date_to: localDateIso(),
  currency_display: "ARS",
  compare_previous: true,
  compare_yoy: false
});

const parseAnalyticsFilters = (raw: string | null): AnalyticsFilterState => {
  const defaults = defaultAnalyticsFilters();
  if (!raw) return defaults;
  try {
    const parsed = JSON.parse(raw) as Partial<AnalyticsFilterState>;
    return {
      date_from: typeof parsed.date_from === "string" && parsed.date_from ? parsed.date_from : defaults.date_from,
      date_to: typeof parsed.date_to === "string" && parsed.date_to ? parsed.date_to : defaults.date_to,
      currency_display:
        parsed.currency_display === "ARS" || parsed.currency_display === "USD" || parsed.currency_display === "BOTH"
          ? parsed.currency_display
          : defaults.currency_display,
      compare_previous: typeof parsed.compare_previous === "boolean" ? parsed.compare_previous : defaults.compare_previous,
      compare_yoy: typeof parsed.compare_yoy === "boolean" ? parsed.compare_yoy : defaults.compare_yoy
    };
  } catch {
    return defaults;
  }
};

function usePersistedAnalyticsFilters(routeName: string) {
  const { session } = useSession();
  const storageKey = useMemo(() => analyticsFilterStorageKey(session.hotelId, routeName), [routeName, session.hotelId]);
  const [filters, setFilters] = useState<AnalyticsFilterState>(() => {
    if (typeof window === "undefined") return defaultAnalyticsFilters();
    return parseAnalyticsFilters(storageKey ? window.sessionStorage.getItem(storageKey) : null);
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    setFilters(parseAnalyticsFilters(storageKey ? window.sessionStorage.getItem(storageKey) : null));
  }, [storageKey]);

  useEffect(() => {
    if (typeof window === "undefined" || !storageKey) return;
    window.sessionStorage.setItem(storageKey, JSON.stringify(filters));
  }, [filters, storageKey]);

  return [filters, setFilters] as const;
}

function AnalyticsFilterBar({
  filters,
  onChange,
  includeCurrency = true,
  includeComparators = true
}: {
  filters: AnalyticsFilterState;
  onChange: (next: AnalyticsFilterState) => void;
  includeCurrency?: boolean;
  includeComparators?: boolean;
}) {
  return (
    <div className="grid gap-3 rounded-2xl border border-slate-200 bg-white p-4 shadow-sm lg:grid-cols-2 xl:grid-cols-5">
      <label className="grid gap-1 text-sm">
        <span className="text-slate-600">Date from</span>
        <input
          type="date"
          value={filters.date_from}
          onChange={(event) => onChange({ ...filters, date_from: event.target.value })}
          className="rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-brand-500"
        />
      </label>
      <label className="grid gap-1 text-sm">
        <span className="text-slate-600">Date to</span>
        <input
          type="date"
          value={filters.date_to}
          onChange={(event) => onChange({ ...filters, date_to: event.target.value })}
          className="rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-brand-500"
        />
      </label>
      {includeCurrency ? (
        <label className="grid gap-1 text-sm">
          <span className="text-slate-600">Currency</span>
          <select
            value={filters.currency_display}
            onChange={(event) =>
              onChange({
                ...filters,
                currency_display: event.target.value as AnalyticsFilterState["currency_display"]
              })
            }
            className="rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-brand-500"
          >
            <option value="ARS">ARS</option>
            <option value="USD">USD</option>
            <option value="BOTH">BOTH</option>
          </select>
        </label>
      ) : null}
      {includeComparators ? (
        <>
          <label className="flex items-center gap-2 self-end rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={filters.compare_previous}
              onChange={(event) => onChange({ ...filters, compare_previous: event.target.checked })}
              className="rounded border-slate-300"
            />
            Compare previous
          </label>
          <label className="flex items-center gap-2 self-end rounded-lg border border-slate-200 px-3 py-2 text-sm text-slate-700">
            <input
              type="checkbox"
              checked={filters.compare_yoy}
              onChange={(event) => onChange({ ...filters, compare_yoy: event.target.checked })}
              className="rounded border-slate-300"
            />
            Compare YoY
          </label>
        </>
      ) : null}
    </div>
  );
}

const buildQuery = (params: Record<string, string | number | boolean | null | undefined>) => {
  const search = new URLSearchParams();
  Object.entries(params).forEach(([key, value]) => {
    if (value === null || value === undefined || value === "") return;
    search.set(key, String(value));
  });
  const query = search.toString();
  return query ? `?${query}` : "";
};

const tableValue = (value: unknown): string => {
  if (value === null || value === undefined) return "—";
  if (typeof value === "boolean") return value ? "Sí" : "No";
  if (typeof value === "number") return String(value);
  if (typeof value === "string") return value;
  if (Array.isArray(value)) return `${value.length} items`;
  if (typeof value === "object") return JSON.stringify(value);
  return String(value);
};

const sectionLabel = (key: string) =>
  key
    .replace(/_/g, " ")
    .replace(/\b\w/g, (match) => match.toUpperCase())
    .trim();

function usePlan() {
  const { data: subscription } = useSubscriptionStatus();
  return subscription?.plan ?? "starter";
}

function useAnalyticsQuery<T>(path: string, params: Record<string, string | number | boolean | null | undefined> = {}) {
  const query = useQuery({
    queryKey: ["analytics", path, params],
    queryFn: async () => apiFetch<T>(`${path}${buildQuery(params)}`),
    staleTime: 30_000
  });
  return query;
}

function PageShell({
  eyebrow,
  title,
  subtitle,
  children,
  actions
}: {
  eyebrow: string;
  title: string;
  subtitle: string;
  children: ReactNode;
  actions?: ReactNode;
}) {
  return (
    <div className="space-y-6">
      <div className="rounded-3xl border border-slate-200 bg-gradient-to-br from-slate-950 via-slate-900 to-emerald-950 p-6 text-white shadow-xl">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div className="max-w-3xl">
            <p className="text-xs uppercase tracking-[0.24em] text-emerald-300">{eyebrow}</p>
            <h1 className="mt-2 text-3xl font-semibold tracking-tight">{title}</h1>
            <p className="mt-3 max-w-2xl text-sm text-slate-200">{subtitle}</p>
          </div>
          {actions && <div className="flex flex-wrap gap-2">{actions}</div>}
        </div>
      </div>
      {children}
    </div>
  );
}

function MetricGrid({ cards }: { cards: Array<Record<string, unknown>> }) {
  const mapped = cards.map((card) => ({
    label: String(card.card_code || card.label || "Métrica"),
    value:
      card.value_ars !== undefined
        ? formatMoney(Number(card.value_ars || 0), "ARS")
        : card.value_usd !== undefined
          ? formatMoney(Number(card.value_usd || 0), "USD")
          : card.value_pct !== undefined
            ? `${card.value_pct}%`
            : card.value_count !== undefined
              ? String(card.value_count)
              : tableValue(card.value ?? card.summary ?? "—"),
    helper: String(card.label || card.card_code || ""),
    tone: card.value_pct !== undefined && Number(card.value_pct) < 50 ? ("danger" as const) : ("default" as const)
  }));
  return (
    <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
      {mapped.map((card) => (
        <StatCard key={card.label} label={card.label} value={card.value} helper={card.helper} tone={card.tone} />
      ))}
    </div>
  );
}

function SectionTables({ data }: { data: Record<string, unknown> }) {
  const entries = Object.entries(data).filter(([key]) => key !== "cards");
  if (entries.length === 0) {
    return null;
  }
  return (
    <div className="grid gap-4 xl:grid-cols-2">
      {entries.map(([key, value]) => {
        if (Array.isArray(value)) {
          const rows = value.filter((item): item is Record<string, unknown> => Boolean(item && typeof item === "object"));
          const headers = rows.reduce<string[]>((acc, row) => {
            Object.keys(row).forEach((field) => {
              if (!acc.includes(field)) acc.push(field);
            });
            return acc;
          }, []);
          return (
            <div key={key} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <h2 className="text-sm font-semibold text-slate-900">{sectionLabel(key)}</h2>
                <span className="text-xs text-slate-500">{rows.length} filas</span>
              </div>
              <div className="mt-3 overflow-auto">
                <table className="min-w-full divide-y divide-slate-200 text-xs">
                  <thead className="bg-slate-50 text-left uppercase text-slate-500">
                    <tr>
                      {headers.map((header) => (
                        <th key={header} className="px-3 py-2">
                          {sectionLabel(header)}
                        </th>
                      ))}
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-slate-200">
                    {rows.map((row, index) => (
                      <tr key={`${key}-${index}`}>
                        {headers.map((header) => (
                          <td key={header} className="px-3 py-2 text-slate-700">
                            {tableValue(row[header])}
                          </td>
                        ))}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          );
        }
        if (value && typeof value === "object") {
          const rows = Object.entries(value as Record<string, unknown>);
          return (
            <div key={key} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-900">{sectionLabel(key)}</h2>
              <div className="mt-3 grid gap-2">
                {rows.map(([field, item]) => (
                  <div key={field} className="flex items-center justify-between gap-3 rounded-lg bg-slate-50 px-3 py-2 text-xs">
                    <span className="font-medium text-slate-600">{sectionLabel(field)}</span>
                    <span className="text-slate-900">{tableValue(item)}</span>
                  </div>
                ))}
              </div>
            </div>
          );
        }
        return (
          <div key={key} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900">{sectionLabel(key)}</h2>
            <p className="mt-2 text-sm text-slate-700">{tableValue(value)}</p>
          </div>
        );
      })}
    </div>
  );
}

function ReportScreen({
  title,
  subtitle,
  path,
  routeName,
  params
}: {
  title: string;
  subtitle: string;
  path: string;
  routeName: string;
  params?: Record<string, string | number | boolean | null | undefined>;
}) {
  const [filters, setFilters] = usePersistedAnalyticsFilters(routeName);
  const queryParams = useMemo(
    () => ({
      ...params,
      date_from: filters.date_from,
      date_to: filters.date_to,
      currency_display: filters.currency_display,
      compare_previous: filters.compare_previous,
      compare_yoy: filters.compare_yoy
    }),
    [filters, params]
  );
  const query = useAnalyticsQuery<AnalyticsEnvelope>(path, queryParams);
  const report = query.data;
  return (
    <PageShell
      eyebrow="Analytics"
      title={title}
      subtitle={subtitle}
      actions={
        <>
          <Link to="/analytics" className="rounded-full border border-white/20 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10">
            Volver
          </Link>
          <Link to="/analytics/operations" className="rounded-full border border-emerald-400/30 bg-emerald-400/15 px-4 py-2 text-sm font-semibold text-emerald-100 hover:bg-emerald-400/25">
            Operación
          </Link>
        </>
      }
    >
      <AnalyticsFilterBar filters={filters} onChange={setFilters} />
      {query.isLoading && <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">Cargando analytics...</div>}
      {query.isError && <div className="rounded-2xl border border-rose-200 bg-rose-50 p-6 text-sm text-rose-800">No se pudo cargar analytics.</div>}
      {report && (
        <div className="space-y-4">
          {"data" in report && Array.isArray((report.data as Record<string, unknown>).cards) && (
            <MetricGrid cards={(report.data as Record<string, unknown>).cards as Array<Record<string, unknown>>} />
          )}
          <SectionTables data={report.data} />
        </div>
      )}
    </PageShell>
  );
}

function StarterLandingScreen() {
  const [filters, setFilters] = usePersistedAnalyticsFilters("starter");
  const query = useAnalyticsQuery<AnalyticsStarterSummary>("/api/analytics/starter-summary", {
    date_from: filters.date_from,
    date_to: filters.date_to
  });
  const cards = query.data?.data.cards ?? [];
  return (
    <PageShell
      eyebrow="Starter"
      title="Analytics Starter"
      subtitle="Vista resumida para hoteles Starter. El módulo completo queda disponible en Pro y Ultra."
      actions={
        <Link to="/settings/subscription" className="rounded-full bg-amber-400 px-4 py-2 text-sm font-semibold text-slate-950 hover:bg-amber-300">
          Subir de plan
        </Link>
      }
    >
      <AnalyticsFilterBar filters={filters} onChange={setFilters} includeCurrency={false} includeComparators={false} />
      <div className="grid gap-4 lg:grid-cols-[1.2fr_0.8fr]">
        <div className="rounded-2xl border border-amber-200 bg-amber-50 p-5 shadow-sm">
          <p className="text-xs uppercase tracking-wide text-amber-700">Resumen Starter</p>
          <div className="mt-4">
            {query.isLoading && <p className="text-sm text-amber-800">Cargando tarjetas resumidas...</p>}
            {cards.length > 0 && <MetricGrid cards={cards} />}
          </div>
        </div>
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Qué incluye Pro y Ultra</h2>
          <ul className="mt-3 space-y-2 text-sm text-slate-700">
            <li>• Analytics completo con comparadores y drill-down.</li>
            <li>• Exportes PNG/CSV en Pro.</li>
            <li>• Exportes XLSX, IA Gemma, alertas y snooze en Ultra.</li>
          </ul>
        </div>
      </div>
    </PageShell>
  );
}

function FullAnalyticsLanding() {
  return (
    <ReportScreen
      title="Analytics"
      subtitle="Resumen ejecutivo del hotel activo con comparadores, canales, segmentos y operación."
      path="/api/analytics/home"
      routeName="home"
    />
  );
}

function PlanGuard({ children }: { children: React.ReactNode }) {
  const plan = usePlan();
  if ((planRank[plan] ?? 0) <= planRank.starter) {
    return <Navigate to="/analytics" replace />;
  }
  return <>{children}</>;
}

function UltraGuard({ children }: { children: React.ReactNode }) {
  const plan = usePlan();
  if ((planRank[plan] ?? 0) < planRank.ultra) {
    return <Navigate to="/analytics" replace />;
  }
  return <>{children}</>;
}

export function AnalyticsHomePage() {
  const plan = usePlan();
  if ((planRank[plan] ?? 0) <= planRank.starter) {
    return <StarterLandingScreen />;
  }
  return <FullAnalyticsLanding />;
}

export function AnalyticsRoomsPage() {
  return (
    <PlanGuard>
      <ReportScreen title="Habitaciones" subtitle="Rendimiento y ocupación por habitación." path="/api/analytics/rooms" routeName="rooms" />
    </PlanGuard>
  );
}

export function AnalyticsRoomDetailPage() {
  const { roomId } = useParams();
  return (
    <PlanGuard>
      <ReportScreen
        title={`Habitación ${roomId ?? ""}`}
        subtitle="Detalle operativo y estados nocturnos por habitación."
        path={roomId ? `/api/analytics/rooms/${roomId}` : "/api/analytics/rooms/0"}
        routeName="room-detail"
      />
    </PlanGuard>
  );
}

export function AnalyticsCategoryDetailPage() {
  const { categoryId } = useParams();
  return (
    <PlanGuard>
      <ReportScreen
        title={`Categoría ${categoryId ?? ""}`}
        subtitle="Detalle de categoría con métricas y comportamiento reciente."
        path={categoryId ? `/api/analytics/categories/${categoryId}` : "/api/analytics/categories/0"}
        routeName="category-detail"
      />
    </PlanGuard>
  );
}

export function AnalyticsSegmentsPage() {
  return (
    <PlanGuard>
      <ReportScreen title="Segmentos" subtitle="Lectura por segmento de huésped." path="/api/analytics/segments" routeName="segments" />
    </PlanGuard>
  );
}

export function AnalyticsCompanyDetailPage() {
  const { companyId } = useParams();
  return (
    <PlanGuard>
      <ReportScreen
        title={`Empresa ${companyId ?? ""}`}
        subtitle="Detalle de company y su comportamiento en analytics."
        path={companyId ? `/api/analytics/companies/${companyId}` : "/api/analytics/companies/0"}
        routeName="company-detail"
      />
    </PlanGuard>
  );
}

export function AnalyticsChannelsPage() {
  return (
    <PlanGuard>
      <ReportScreen title="Canales" subtitle="Mix de canales y performance por origen." path="/api/analytics/channels" routeName="channels" />
    </PlanGuard>
  );
}

export function AnalyticsOperationsPage() {
  return (
    <PlanGuard>
      <ReportScreen title="Operaciones" subtitle="Eventos y señales operativas del hotel." path="/api/analytics/operations" routeName="operations" />
    </PlanGuard>
  );
}

export function AnalyticsAIChatPage() {
  const [filters, setFilters] = usePersistedAnalyticsFilters("ai-chat");
  const [message, setMessage] = useState("");
  const [history, setHistory] = useState<ChatMessage[]>([]);
  const statusQuery = useAnalyticsQuery<AnalyticsAIStatus>("/api/analytics/insights/status");

  const chatMutation = useMutation({
    mutationFn: async (text: string) =>
      apiFetch<AnalyticsAIChatResponse>("/api/analytics/ai-chat", {
        method: "POST",
        data: {
          message: text,
          date_from: filters.date_from,
          date_to: filters.date_to,
          currency_display: filters.currency_display,
          compare_previous: filters.compare_previous,
          compare_yoy: filters.compare_yoy
        }
      }),
    onSuccess: (response, text) => {
      setHistory((current) => [
        ...current,
        { role: "user", text },
        {
          role: "assistant",
          text: response.answer,
          warnings: response.warnings,
          recommendations: response.recommendations
        }
      ]);
      setMessage("");
    }
  });

  const suggestions = [
    "Resumí el estado del hotel este mes",
    "Detectá anomalías",
    "Qué canal está rindiendo mejor",
    "Qué categorías conviene mejorar",
    "Cómo puedo aumentar ocupación"
  ];
  const status = statusQuery.data;
  const aiDisconnected = status ? !status.analytics_ai_enabled || !status.runtime_healthy : false;
  const errorMessage = chatMutation.error instanceof Error ? chatMutation.error.message : null;

  return (
    <UltraGuard>
      <PageShell
        eyebrow="Analytics IA"
        title="Asistente IA del hotel"
        subtitle="Consultas acotadas al contexto de Analytics del hotel activo."
        actions={
          <Link to="/analytics" className="rounded-full border border-white/20 px-4 py-2 text-sm font-semibold text-white hover:bg-white/10">
            Dashboard
          </Link>
        }
      >
        <AnalyticsFilterBar filters={filters} onChange={setFilters} />
        {aiDisconnected ? (
          <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900">
            La IA todavía no está conectada. Configurá el proveedor de IA para usar el asistente.
          </div>
        ) : null}
        <div className="grid gap-4 lg:grid-cols-[0.75fr_1.25fr]">
          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-900">Sugerencias rápidas</h2>
            <div className="mt-3 grid gap-2">
              {suggestions.map((suggestion) => (
                <button
                  key={suggestion}
                  type="button"
                  onClick={() => setMessage(suggestion)}
                  className="rounded-lg border border-slate-200 px-3 py-2 text-left text-sm text-slate-700 hover:border-brand-300 hover:bg-brand-50"
                >
                  {suggestion}
                </button>
              ))}
            </div>
            {status ? (
              <div className="mt-4 rounded-lg bg-slate-50 p-3 text-xs text-slate-600">
                <div>Provider: {status.provider}</div>
                <div>Modelo: {status.effective_model || "sin configurar"}</div>
                <div>Estado: {status.runtime_status}</div>
              </div>
            ) : null}
          </div>

          <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
            <div className="min-h-72 space-y-3">
              {history.length === 0 ? (
                <div className="rounded-xl border border-dashed border-slate-300 p-6 text-sm text-slate-500">
                  Hacé una pregunta sobre ocupación, canales, habitaciones, categorías, margen u operación del hotel.
                </div>
              ) : (
                history.map((item, index) => (
                  <div
                    key={`${item.role}-${index}`}
                    className={`rounded-xl px-4 py-3 text-sm ${
                      item.role === "user" ? "ml-auto max-w-[85%] bg-brand-600 text-white" : "mr-auto max-w-[92%] bg-slate-100 text-slate-800"
                    }`}
                  >
                    <p>{item.text}</p>
                    {item.warnings?.length ? <p className="mt-2 text-xs opacity-80">Alertas: {item.warnings.join(" · ")}</p> : null}
                    {item.recommendations?.length ? <p className="mt-2 text-xs opacity-80">Recomendaciones: {item.recommendations.join(" · ")}</p> : null}
                  </div>
                ))
              )}
            </div>
            {errorMessage ? (
              <div className="mt-3 rounded-lg border border-rose-200 bg-rose-50 px-3 py-2 text-sm text-rose-800">{errorMessage}</div>
            ) : null}
            <form
              className="mt-4 flex flex-col gap-2 sm:flex-row"
              onSubmit={(event) => {
                event.preventDefault();
                const text = message.trim();
                if (text) chatMutation.mutate(text);
              }}
            >
              <input
                value={message}
                onChange={(event) => setMessage(event.target.value)}
                placeholder="Preguntá sobre métricas, anomalías, canales o pricing"
                className="min-h-11 flex-1 rounded-lg border border-slate-300 px-3 py-2 text-sm outline-none focus:border-brand-500"
              />
              <button
                type="submit"
                disabled={chatMutation.isPending || !message.trim()}
                className="rounded-lg bg-brand-600 px-5 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:cursor-not-allowed disabled:bg-slate-300"
              >
                {chatMutation.isPending ? "Enviando..." : "Enviar"}
              </button>
            </form>
          </div>
        </div>
      </PageShell>
    </UltraGuard>
  );
}

export function CompaniesSettingsPage() {
  const plan = usePlan();
  const queryClient = useQueryClient();
  const [editing, setEditing] = useState<Company | null>(null);
  const [form, setForm] = useState({
    legal_name: "",
    display_name: "",
    tax_id: "",
    country_code: "AR",
    notes: ""
  });

  const companiesQuery = useQuery({
    queryKey: ["companies"],
    queryFn: async () => apiFetch<Company[]>("/api/companies"),
    staleTime: 30_000
  });

  const createMutation = useMutation({
    mutationFn: async () =>
      apiFetch<Company>("/api/companies", {
        method: "POST",
        data: {
          legal_name: form.legal_name,
          display_name: form.display_name,
          tax_id: form.tax_id || null,
          country_code: form.country_code || null,
          notes: form.notes || null
        }
      }),
    onSuccess: async () => {
      setForm({ legal_name: "", display_name: "", tax_id: "", country_code: "AR", notes: "" });
      await queryClient.invalidateQueries({ queryKey: ["companies"] });
    }
  });

  const patchMutation = useMutation({
    mutationFn: async () =>
      editing &&
      apiFetch<Company>(`/api/companies/${editing.id}`, {
        method: "PATCH",
        data: {
          legal_name: form.legal_name || undefined,
          display_name: form.display_name || undefined,
          tax_id: form.tax_id || undefined,
          country_code: form.country_code || undefined,
          notes: form.notes || undefined
        }
      }),
    onSuccess: async () => {
      setEditing(null);
      await queryClient.invalidateQueries({ queryKey: ["companies"] });
    }
  });

  const deactivateMutation = useMutation({
    mutationFn: async (companyId: number) => apiFetch(`/api/companies/${companyId}/deactivate`, { method: "POST" }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["companies"] })
  });
  const reactivateMutation = useMutation({
    mutationFn: async (companyId: number) => apiFetch(`/api/companies/${companyId}/reactivate`, { method: "POST" }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["companies"] })
  });

  const companies = companiesQuery.data || [];
  if ((planRank[plan] ?? 0) < planRank.pro) {
    return <Navigate to="/analytics" replace />;
  }

  return (
    <PageShell
      eyebrow="Settings"
      title="Companies"
      subtitle="CRUD completo de compañías para el hotel activo."
      actions={<Link to="/analytics" className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800">Analytics</Link>}
    >
      <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">{editing ? "Editar company" : "Nueva company"}</h2>
          <div className="mt-4 grid gap-3">
            {[
              ["legal_name", "Legal name"],
              ["display_name", "Display name"],
              ["tax_id", "Tax ID"],
              ["country_code", "Country code"],
              ["notes", "Notes"]
            ].map(([key, label]) => (
              <label key={key} className="grid gap-1 text-sm">
                <span className="text-slate-600">{label}</span>
                <input
                  value={(form as Record<string, string>)[key]}
                  onChange={(event) => setForm((current) => ({ ...current, [key]: event.target.value }))}
                  className="rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-brand-500"
                />
              </label>
            ))}
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <button
              type="button"
              onClick={() => (editing ? patchMutation.mutate() : createMutation.mutate())}
              className="rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
            >
              {editing ? "Guardar" : "Crear"}
            </button>
            {editing && (
              <button
                type="button"
                onClick={() => {
                  setEditing(null);
                  setForm({ legal_name: "", display_name: "", tax_id: "", country_code: "AR", notes: "" });
                }}
                className="rounded-lg border border-slate-300 px-4 py-2 text-sm font-semibold text-slate-700"
              >
                Cancelar
              </button>
            )}
          </div>
        </div>

        <div className="space-y-3">
          {companies.map((company) => (
            <div key={company.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Company #{company.id}</p>
                  <h3 className="text-lg font-semibold text-slate-900">{company.display_name}</h3>
                  <p className="text-sm text-slate-600">{company.legal_name}</p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <button
                    type="button"
                    onClick={() => {
                      setEditing(company);
                      setForm({
                        legal_name: company.legal_name,
                        display_name: company.display_name,
                        tax_id: company.tax_id || "",
                        country_code: company.country_code || "AR",
                        notes: company.notes || ""
                      });
                    }}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700"
                  >
                    Editar
                  </button>
                  {company.is_active ? (
                    <button
                      type="button"
                      onClick={() => deactivateMutation.mutate(company.id)}
                      className="rounded-lg border border-rose-300 px-3 py-2 text-xs font-semibold text-rose-700"
                    >
                      Desactivar
                    </button>
                  ) : (
                    <button
                      type="button"
                      onClick={() => reactivateMutation.mutate(company.id)}
                      className="rounded-lg border border-emerald-300 px-3 py-2 text-xs font-semibold text-emerald-700"
                    >
                      Reactivar
                    </button>
                  )}
                  <Link
                    to={`/analytics/companies/${company.id}`}
                    className="rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700"
                  >
                    Ver analytics
                  </Link>
                </div>
              </div>
              <div className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
                <div>Tax ID: {company.tax_id || "—"}</div>
                <div>Country: {company.country_code || "—"}</div>
                <div>Status: {company.is_active ? "Activa" : "Inactiva"}</div>
                <div>Notas: {company.notes || "—"}</div>
              </div>
            </div>
          ))}
          {companies.length === 0 && <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">Sin companies cargadas.</div>}
        </div>
      </div>
    </PageShell>
  );
}

export function RoomStateEventsPage() {
  const plan = usePlan();
  const queryClient = useQueryClient();
  const [form, setForm] = useState<RoomStateEventCreate>({
    room_id: 0,
    event_type: "maintenance",
    reason_code: "inspection",
    reason_note: "",
    started_at: new Date().toISOString()
  });

  const eventsQuery = useQuery({
    queryKey: ["room-state-events"],
    queryFn: async () => apiFetch<RoomStateEvent[]>("/api/room-state-events"),
    staleTime: 10_000
  });

  const createMutation = useMutation({
    mutationFn: async () =>
      apiFetch<RoomStateEvent>("/api/room-state-events", {
        method: "POST",
        data: {
          ...form,
          reason_note: form.reason_note || null,
          started_at: form.started_at || null
        }
      }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["room-state-events"] })
  });

  const closeMutation = useMutation({
    mutationFn: async (eventId: number) => apiFetch(`/api/room-state-events/${eventId}/close`, { method: "POST" }),
    onSuccess: async () => queryClient.invalidateQueries({ queryKey: ["room-state-events"] })
  });

  const events = eventsQuery.data || [];
  if ((planRank[plan] ?? 0) < planRank.pro) {
    return <Navigate to="/analytics" replace />;
  }

  return (
    <PageShell
      eyebrow="Operacion"
      title="Room state events"
      subtitle="Eventos operativos de bloqueo y cierre por habitación."
      actions={<Link to="/analytics" className="rounded-full border border-slate-300 bg-white px-4 py-2 text-sm font-semibold text-slate-800">Analytics</Link>}
    >
      <div className="grid gap-4 lg:grid-cols-[0.9fr_1.1fr]">
        <div className="rounded-2xl border border-slate-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-semibold text-slate-900">Nuevo evento</h2>
          <div className="mt-4 grid gap-3">
            <label className="grid gap-1 text-sm">
              <span className="text-slate-600">Room ID</span>
              <input
                type="number"
                value={form.room_id || ""}
                onChange={(event) => setForm((current) => ({ ...current, room_id: Number(event.target.value) }))}
                className="rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-brand-500"
              />
            </label>
            <label className="grid gap-1 text-sm">
              <span className="text-slate-600">Tipo</span>
              <select
                value={form.event_type}
                onChange={(event) => setForm((current) => ({ ...current, event_type: event.target.value as RoomStateEventCreate["event_type"] }))}
                className="rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-brand-500"
              >
                <option value="out_of_service">Out of service</option>
                <option value="maintenance">Maintenance</option>
                <option value="housekeeping_block">Housekeeping block</option>
                <option value="renovation">Renovation</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm">
              <span className="text-slate-600">Motivo</span>
              <select
                value={form.reason_code}
                onChange={(event) => setForm((current) => ({ ...current, reason_code: event.target.value as RoomStateEventCreate["reason_code"] }))}
                className="rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-brand-500"
              >
                <option value="plumbing">Plumbing</option>
                <option value="electrical">Electrical</option>
                <option value="furniture">Furniture</option>
                <option value="deep_clean">Deep clean</option>
                <option value="inspection">Inspection</option>
                <option value="other">Other</option>
              </select>
            </label>
            <label className="grid gap-1 text-sm">
              <span className="text-slate-600">Nota</span>
              <input
                value={form.reason_note || ""}
                onChange={(event) => setForm((current) => ({ ...current, reason_note: event.target.value }))}
                className="rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-brand-500"
              />
            </label>
            <label className="grid gap-1 text-sm">
              <span className="text-slate-600">Inicio</span>
              <input
                value={form.started_at || ""}
                onChange={(event) => setForm((current) => ({ ...current, started_at: event.target.value }))}
                className="rounded-lg border border-slate-300 px-3 py-2 outline-none focus:border-brand-500"
              />
            </label>
          </div>
          <button
            type="button"
            onClick={() => createMutation.mutate()}
            className="mt-4 rounded-lg bg-brand-600 px-4 py-2 text-sm font-semibold text-white hover:bg-brand-700"
          >
            Crear evento
          </button>
        </div>

        <div className="space-y-3">
          {events.map((event) => (
            <div key={event.id} className="rounded-2xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <p className="text-xs uppercase tracking-wide text-slate-500">Event #{event.id}</p>
                  <h3 className="text-lg font-semibold text-slate-900">{event.event_type}</h3>
                  <p className="text-sm text-slate-600">Room {event.room_id} · {event.reason_code}</p>
                </div>
                <div className="flex gap-2">
                  {event.ended_at ? (
                    <span className="rounded-full bg-emerald-100 px-3 py-1 text-xs font-semibold text-emerald-800">Cerrado</span>
                  ) : (
                    <button
                      type="button"
                      onClick={() => closeMutation.mutate(event.id)}
                      className="rounded-lg border border-emerald-300 px-3 py-2 text-xs font-semibold text-emerald-700"
                    >
                      Cerrar
                    </button>
                  )}
                </div>
              </div>
              <div className="mt-3 grid gap-2 text-xs text-slate-600 sm:grid-cols-2">
                <div>Inicio: {event.started_at}</div>
                <div>Fin: {event.ended_at || "Abierto"}</div>
                <div>Creado por: {event.created_by_user_id}</div>
                <div>Cerrado por: {event.closed_by_user_id || "—"}</div>
                <div className="sm:col-span-2">Nota: {event.reason_note || "—"}</div>
              </div>
            </div>
          ))}
          {events.length === 0 && <div className="rounded-2xl border border-slate-200 bg-white p-6 text-sm text-slate-500">Sin eventos cargados.</div>}
        </div>
      </div>
    </PageShell>
  );
}
