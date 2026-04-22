import { useEffect, useState } from "react";

import MasterStatCard from "../../components/StatCard";
import { ApiError } from "../../api/client";
import { masterAdminFetch, type MasterDashboardSummary, type MasterHotelRow } from "../api";
import { useMasterAdminSession } from "../session";

export function MasterAdminDashboardPage() {
  const { user } = useMasterAdminSession();
  const [summary, setSummary] = useState<MasterDashboardSummary | null>(null);
  const [hotels, setHotels] = useState<MasterHotelRow[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      setLoading(true);
      setError(null);
      try {
        const [summaryData, hotelsData] = await Promise.all([
          masterAdminFetch<MasterDashboardSummary>("/api/master-admin/dashboard/summary"),
          masterAdminFetch<{ items: MasterHotelRow[] }>("/api/master-admin/dashboard/hotels")
        ]);
        if (cancelled) return;
        setSummary(summaryData);
        setHotels(hotelsData.items);
      } catch (err) {
        if (cancelled) return;
        if (err instanceof ApiError) setError(err.message);
        else setError("No se pudo cargar el dashboard master");
      } finally {
        if (!cancelled) setLoading(false);
      }
    };
    void load();
    return () => {
      cancelled = true;
    };
  }, []);

  if (loading) {
    return (
      <div className="grid min-h-[60vh] place-items-center text-slate-200">
        <div className="rounded-3xl border border-white/10 bg-white/5 px-6 py-4 text-sm">Cargando dashboard...</div>
      </div>
    );
  }

  return (
    <div className="space-y-6 pb-10">
      <section className="rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/10 backdrop-blur">
        <p className="text-xs uppercase tracking-[0.35em] text-amber-300/80">Overview</p>
        <h2 className="mt-2 text-3xl font-semibold text-white">Operación de plataforma</h2>
        <p className="mt-2 max-w-3xl text-sm text-slate-300">
          Panel separado para administrar policy central, email, Stripe base y auditoría sin tocar la sesión operativa del PMS.
        </p>
        <p className="mt-4 text-sm text-slate-400">Operador activo: {user?.email}</p>
      </section>

      {error && <div className="rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">{error}</div>}

      {summary && (
        <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-5">
          <MasterStatCard label="Hoteles" value={summary.counts.hotels} helper="Tenants visibles" tone="info" />
          <MasterStatCard label="Activas" value={summary.counts.active_subscriptions} helper="Suscripciones activas" tone="success" />
          <MasterStatCard label="Trialing" value={summary.counts.trialing} helper="En periodo de prueba" />
          <MasterStatCard label="Past due" value={summary.counts.past_due} helper="Cobranza / gracia" tone="danger" />
        </section>
      )}

      {summary && (
        <section className="grid gap-4 lg:grid-cols-[1.3fr_0.7fr]">
          <div className="rounded-[2rem] border border-white/10 bg-slate-950/50 p-5 shadow-xl shadow-black/10">
            <div className="mb-4 flex items-center justify-between">
              <h3 className="text-lg font-semibold text-white">Eventos recientes</h3>
              <span className="text-xs uppercase tracking-[0.25em] text-slate-400">Audit trail</span>
            </div>
            <div className="space-y-3">
              {summary.recent_events.length === 0 && <p className="text-sm text-slate-400">Sin eventos todavía.</p>}
              {summary.recent_events.map((event) => (
                <div key={event.id} className="rounded-2xl border border-white/5 bg-white/5 p-4 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <p className="font-medium text-white">{event.action}</p>
                    <span className="rounded-full border border-white/10 px-2 py-0.5 text-xs text-slate-300">{event.outcome}</span>
                  </div>
                  <p className="mt-1 text-xs text-slate-400">
                    {event.target_type || "system"} {event.target_id ? `· ${event.target_id}` : ""}
                  </p>
                </div>
              ))}
            </div>
          </div>

          <div className="rounded-[2rem] border border-white/10 bg-slate-950/50 p-5 shadow-xl shadow-black/10">
            <h3 className="text-lg font-semibold text-white">Policy actual</h3>
            <dl className="mt-4 space-y-3 text-sm">
              <div className="flex items-center justify-between">
                <dt className="text-slate-400">Enabled</dt>
                <dd className="text-white">{summary.policy.enabled ? "Sí" : "No"}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-400">Active</dt>
                <dd className="text-white">{summary.policy.allow_active ? "Sí" : "No"}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-400">Trialing</dt>
                <dd className="text-white">{summary.policy.allow_trialing ? "Sí" : "No"}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-400">Exempt hotels</dt>
                <dd className="text-white">{summary.policy.exempt_hotel_ids.length}</dd>
              </div>
              <div className="flex items-center justify-between">
                <dt className="text-slate-400">Exempt users</dt>
                <dd className="text-white">{summary.policy.exempt_user_ids.length}</dd>
              </div>
            </dl>
          </div>
        </section>
      )}

      <section className="rounded-[2rem] border border-white/10 bg-slate-950/50 p-5 shadow-xl shadow-black/10">
        <div className="mb-4 flex items-center justify-between">
          <h3 className="text-lg font-semibold text-white">Hoteles</h3>
          <span className="text-xs uppercase tracking-[0.25em] text-slate-400">{hotels.length} filas</span>
        </div>
        <div className="overflow-x-auto">
          <table className="min-w-full border-separate border-spacing-y-2 text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-[0.2em] text-slate-400">
                <th className="px-3 py-2">Hotel</th>
                <th className="px-3 py-2">Plan</th>
                <th className="px-3 py-2">Estado</th>
                <th className="px-3 py-2">Can write</th>
                <th className="px-3 py-2">Reason</th>
              </tr>
            </thead>
            <tbody>
              {hotels.map((hotel) => (
                <tr key={hotel.hotel_id} className="rounded-2xl bg-white/5 text-slate-100">
                  <td className="rounded-l-2xl px-3 py-3">
                    <div className="font-medium">{hotel.hotel_name}</div>
                    <div className="text-xs text-slate-400">#{hotel.hotel_id}</div>
                  </td>
                  <td className="px-3 py-3">{hotel.plan}</td>
                  <td className="px-3 py-3">{hotel.status}</td>
                  <td className="px-3 py-3">{hotel.can_write ? "Sí" : "No"}</td>
                  <td className="rounded-r-2xl px-3 py-3 text-slate-300">{hotel.reason}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
