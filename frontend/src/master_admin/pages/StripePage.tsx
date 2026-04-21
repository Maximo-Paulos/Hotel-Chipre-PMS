import { useEffect, useState } from "react";

import { masterAdminFetch } from "../api";

type StripeConfig = {
  configured: boolean;
  secret_source: string;
  tolerance_seconds: number;
};

export function MasterAdminStripePage() {
  const [config, setConfig] = useState<StripeConfig | null>(null);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    void masterAdminFetch<StripeConfig>("/api/master-admin/stripe/config")
      .then(setConfig)
      .catch(() => setMessage("No se pudo cargar la configuración de Stripe."));
  }, []);

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/10 backdrop-blur">
        <p className="text-xs uppercase tracking-[0.35em] text-amber-300/80">Stripe base</p>
        <h2 className="mt-2 text-3xl font-semibold text-white">Webhook firmado</h2>
        <p className="mt-2 text-sm text-slate-300">
          El backend acepta eventos firmados con el secret dedicado y los registra en la auditoría interna.
        </p>
      </section>

      {message && <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100">{message}</div>}

      {config && (
        <section className="grid gap-4 md:grid-cols-3">
          <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Configured</p>
            <p className="mt-2 text-lg font-semibold text-white">{config.configured ? "Yes" : "No"}</p>
          </div>
          <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Secret source</p>
            <p className="mt-2 text-lg font-semibold text-white">{config.secret_source}</p>
          </div>
          <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Tolerance</p>
            <p className="mt-2 text-lg font-semibold text-white">{config.tolerance_seconds}s</p>
          </div>
        </section>
      )}

      <section className="rounded-[2rem] border border-white/10 bg-slate-950/50 p-5 text-sm text-slate-300">
        <p className="font-medium text-white">Webhook endpoint</p>
        <p className="mt-2">`POST /api/master-admin/stripe/webhook`</p>
        <p className="mt-2">
          Requiere `Stripe-Signature` válido y `MASTER_STRIPE_WEBHOOK_SECRET` en el backend.
        </p>
      </section>
    </div>
  );
}
