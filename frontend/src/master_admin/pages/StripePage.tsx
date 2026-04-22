import { useCallback, useEffect, useState, type FormEvent } from "react";

import { ApiError } from "../../api/client";
import { masterAdminFetch, type MasterStripeConfig } from "../api";

type StripeConnectPayload = {
  stripe_secret_key: string;
  webhook_secret: string;
  enabled: boolean;
};

export function MasterAdminStripePage() {
  const [config, setConfig] = useState<MasterStripeConfig | null>(null);
  const [stripeSecretKey, setStripeSecretKey] = useState("");
  const [webhookSecret, setWebhookSecret] = useState("");
  const [enabled, setEnabled] = useState(true);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const reload = useCallback(async () => {
    const data = await masterAdminFetch<MasterStripeConfig>("/api/master-admin/stripe/config");
    setConfig(data);
    setEnabled(data.enabled);
  }, []);

  useEffect(() => {
    void reload().catch(() => setMessage("No se pudo cargar la configuracion de Stripe."));
  }, [reload]);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setMessage(null);
    try {
      const payload: StripeConnectPayload = {
        stripe_secret_key: stripeSecretKey,
        webhook_secret: webhookSecret,
        enabled
      };
      const updated = await masterAdminFetch<MasterStripeConfig>("/api/master-admin/stripe/connect", {
        method: "POST",
        data: payload
      });
      setConfig(updated);
      setMessage("Stripe quedo conectado y validado desde el panel owner.");
      setStripeSecretKey("");
    } catch (error) {
      if (error instanceof ApiError) setMessage(error.message);
      else setMessage("No se pudo conectar Stripe.");
    } finally {
      setLoading(false);
    }
  };

  const disconnect = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const updated = await masterAdminFetch<MasterStripeConfig>("/api/master-admin/stripe/disconnect", {
        method: "POST",
        data: {}
      });
      setConfig(updated);
      setStripeSecretKey("");
      setWebhookSecret("");
      setMessage("Stripe quedo desconectado.");
    } catch (error) {
      if (error instanceof ApiError) setMessage(error.message);
      else setMessage("No se pudo desconectar Stripe.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <form onSubmit={submit} className="space-y-6">
      <section className="rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/10 backdrop-blur">
        <p className="text-xs uppercase tracking-[0.35em] text-amber-300/80">Stripe owner</p>
        <h2 className="mt-2 text-3xl font-semibold text-white">Conexion segura desde el panel</h2>
        <p className="mt-2 text-sm text-slate-300">
          El owner carga el secret key y el webhook secret una sola vez. La config queda persistida y el webhook firma contra esa
          configuracion guardada.
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
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Account</p>
            <p className="mt-2 text-lg font-semibold text-white">{config.account_name || config.account_id || "Not connected"}</p>
            {config.account_id && <p className="mt-1 text-sm text-slate-400">{config.account_id}</p>}
          </div>
          <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Webhook</p>
            <p className="mt-2 text-lg font-semibold text-white">{config.webhook_secret_configured ? "Configured" : "Missing"}</p>
            {config.last_error && <p className="mt-1 text-sm text-rose-300">{config.last_error}</p>}
          </div>
        </section>
      )}

      <section className="grid gap-6 lg:grid-cols-[1fr_1fr]">
        <label className="rounded-[2rem] border border-white/10 bg-slate-950/50 p-5">
          <span className="block text-sm font-medium text-slate-200">Stripe secret key</span>
          <input
            type="password"
            required
            value={stripeSecretKey}
            onChange={(event) => setStripeSecretKey(event.target.value)}
            className="mt-3 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none focus:border-amber-300/60"
            placeholder="sk_live_..."
          />
        </label>
        <label className="rounded-[2rem] border border-white/10 bg-slate-950/50 p-5">
          <span className="block text-sm font-medium text-slate-200">Webhook secret</span>
          <input
            type="password"
            required
            value={webhookSecret}
            onChange={(event) => setWebhookSecret(event.target.value)}
            className="mt-3 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none focus:border-amber-300/60"
            placeholder="whsec_..."
          />
        </label>
      </section>

      <label className="flex items-center gap-3 rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
        <input
          type="checkbox"
          checked={enabled}
          onChange={(event) => setEnabled(event.target.checked)}
          className="h-5 w-5 rounded border-white/20 bg-white/10 text-amber-300 focus:ring-amber-300"
        />
        <span className="text-sm text-slate-200">Habilitar Stripe globalmente</span>
      </label>

      <div className="flex flex-wrap gap-3">
        <button
          type="submit"
          disabled={loading}
          className="rounded-2xl bg-amber-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-70"
        >
          {loading ? "Guardando..." : "Conectar Stripe"}
        </button>
        <button
          type="button"
          onClick={() => void disconnect()}
          disabled={loading}
          className="rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-70"
        >
          Desconectar
        </button>
      </div>

      <section className="rounded-[2rem] border border-white/10 bg-slate-950/50 p-5 text-sm text-slate-300">
        <p className="font-medium text-white">Webhook endpoint</p>
        <p className="mt-2">`POST /api/master-admin/stripe/webhook`</p>
        <p className="mt-2">
          La firma se valida contra el secret almacenado en el panel. Si no existe, el webhook falla de forma explicita.
        </p>
      </section>
    </form>
  );
}
