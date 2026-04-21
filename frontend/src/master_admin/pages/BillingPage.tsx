import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "../../api/client";
import { masterAdminFetch, type MasterBillingPolicy } from "../api";

const parseHotelIds = (value: string) =>
  value
    .split(/[\n,]+/)
    .map((entry) => parseInt(entry.trim(), 10))
    .filter((entry) => Number.isInteger(entry) && entry > 0);

export function MasterAdminBillingPage() {
  const [policy, setPolicy] = useState<MasterBillingPolicy | null>(null);
  const [notes, setNotes] = useState("");
  const [exemptHotelIds, setExemptHotelIds] = useState("");
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    const load = async () => {
      const data = await masterAdminFetch<MasterBillingPolicy>("/api/master-admin/billing/policy");
      if (cancelled) return;
      setPolicy(data);
      setNotes(data.notes || "");
      setExemptHotelIds((data.exempt_hotel_ids || []).join(", "));
    };
    void load().catch(() => {
      if (!cancelled) setMessage("No se pudo cargar la policy de billing.");
    });
    return () => {
      cancelled = true;
    };
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!policy) return;
    setSaving(true);
    setMessage(null);
    try {
      const updated = await masterAdminFetch<MasterBillingPolicy>("/api/master-admin/billing/policy", {
        method: "PUT",
        data: {
          enabled: policy.enabled,
          allow_active: policy.allow_active,
          allow_trialing: policy.allow_trialing,
          allow_demo: policy.allow_demo,
          allow_comped: policy.allow_comped,
          allow_past_due_grace: policy.allow_past_due_grace,
          exempt_hotel_ids: parseHotelIds(exemptHotelIds),
          notes
        }
      });
      setPolicy(updated);
      setMessage("Policy actualizada.");
    } catch (error) {
      if (error instanceof ApiError) setMessage(error.message);
      else setMessage("No se pudo actualizar la policy.");
    } finally {
      setSaving(false);
    }
  };

  if (!policy) {
    return (
      <div className="rounded-3xl border border-white/10 bg-white/5 px-6 py-4 text-sm text-slate-200">
        Cargando billing policy...
      </div>
    );
  }

  return (
    <form onSubmit={submit} className="space-y-6">
      <section className="rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/10 backdrop-blur">
        <p className="text-xs uppercase tracking-[0.35em] text-amber-300/80">Billing Policy Engine</p>
        <h2 className="mt-2 text-3xl font-semibold text-white">Paywall central</h2>
        <p className="mt-2 max-w-3xl text-sm text-slate-300">
          El backend evalúa esta policy antes de permitir escrituras cuando la enforcement está activa.
        </p>
      </section>

      {message && <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100">{message}</div>}

      <section className="grid gap-4 md:grid-cols-2 xl:grid-cols-3">
        {[
          ["enabled", "Enabled"],
          ["allow_active", "Allow active"],
          ["allow_trialing", "Allow trialing"],
          ["allow_demo", "Allow demo"],
          ["allow_comped", "Allow comped"],
          ["allow_past_due_grace", "Allow past due grace"]
        ].map(([key, label]) => (
          <label key={key} className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
            <div className="flex items-center justify-between gap-3">
              <span className="text-sm text-slate-200">{label}</span>
              <input
                type="checkbox"
                checked={Boolean(policy[key as keyof MasterBillingPolicy])}
                onChange={(event) =>
                  setPolicy((current) =>
                    current ? { ...current, [key]: event.target.checked } as MasterBillingPolicy : current
                  )
                }
                className="h-5 w-5 rounded border-white/20 bg-white/10 text-amber-300 focus:ring-amber-300"
              />
            </div>
          </label>
        ))}
      </section>

      <section className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <label className="rounded-[2rem] border border-white/10 bg-slate-950/50 p-5">
          <span className="block text-sm font-medium text-slate-200">Exempt hotel IDs</span>
          <textarea
            value={exemptHotelIds}
            onChange={(event) => setExemptHotelIds(event.target.value)}
            rows={8}
            className="mt-3 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-amber-300/60"
            placeholder="1, 7, 12"
          />
          <p className="mt-2 text-xs text-slate-400">Separados por coma o salto de línea.</p>
        </label>

        <label className="rounded-[2rem] border border-white/10 bg-slate-950/50 p-5">
          <span className="block text-sm font-medium text-slate-200">Notes</span>
          <textarea
            value={notes}
            onChange={(event) => setNotes(event.target.value)}
            rows={8}
            className="mt-3 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-amber-300/60"
            placeholder="Motivo operativo, ventana temporal, owner request..."
          />
        </label>
      </section>

      <button
        type="submit"
        disabled={saving}
        className="rounded-2xl bg-amber-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-70"
      >
        {saving ? "Guardando..." : "Guardar policy"}
      </button>
    </form>
  );
}
