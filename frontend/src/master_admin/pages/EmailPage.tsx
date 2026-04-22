import { useCallback, useEffect, useState, type FormEvent } from "react";

import { ApiError } from "../../api/client";
import { masterAdminFetch, type MasterEmailConnectResponse, type MasterEmailStatus } from "../api";

type EmailTestResult = { ok: boolean; provider: string; sender_email?: string | null; provider_message_id?: string | null };

export function MasterAdminEmailPage() {
  const [status, setStatus] = useState<MasterEmailStatus | null>(null);
  const [recipient, setRecipient] = useState("");
  const [subject, setSubject] = useState("Hotel Chipre master panel test");
  const [body, setBody] = useState("Mensaje de prueba desde el panel master.");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  const reloadStatus = useCallback(async () => {
    const data = await masterAdminFetch<MasterEmailStatus>("/api/master-admin/email/status");
    setStatus(data);
  }, []);

  useEffect(() => {
    void reloadStatus().catch(() => setMessage("No se pudo leer el estado del email del sistema."));
  }, [reloadStatus]);

  useEffect(() => {
    const handler = (event: MessageEvent) => {
      if (typeof event.data !== "object" || event.data === null) return;
      if ((event.data as { type?: string }).type !== "master-admin-email-oauth-result") return;
      const payload = event.data as { status?: string; message?: string };
      setMessage(payload.message || "Flujo OAuth completado.");
      void reloadStatus().catch(() => setMessage("No se pudo refrescar el estado del email."));
    };
    window.addEventListener("message", handler);
    return () => window.removeEventListener("message", handler);
  }, [reloadStatus]);

  const startConnect = async () => {
    setLoading(true);
    setMessage(null);
    try {
      const result = await masterAdminFetch<MasterEmailConnectResponse>("/api/master-admin/email/connect", {
        method: "POST",
        data: {}
      });
      if (!result.redirect_url) {
        throw new Error("No se genero la URL de OAuth para Gmail.");
      }
      const popup = window.open(result.redirect_url, "master-admin-gmail-oauth", "width=540,height=720");
      if (!popup) {
        throw new Error("El navegador bloqueo la ventana emergente de OAuth.");
      }
      popup.focus();
      setMessage("Completa la autorizacion de Gmail en la ventana emergente.");
    } catch (error) {
      if (error instanceof ApiError) setMessage(error.message);
      else if (error instanceof Error) setMessage(error.message);
      else setMessage("No se pudo iniciar la conexion de Gmail.");
    } finally {
      setLoading(false);
    }
  };

  const disconnect = async () => {
    setLoading(true);
    setMessage(null);
    try {
      await masterAdminFetch<MasterEmailStatus>("/api/master-admin/email/disconnect", { method: "POST", data: {} });
      await reloadStatus();
      setMessage("La conexion de Gmail quedo desconectada.");
    } catch (error) {
      if (error instanceof ApiError) setMessage(error.message);
      else setMessage("No se pudo desconectar Gmail.");
    } finally {
      setLoading(false);
    }
  };

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setMessage(null);
    try {
      const result = await masterAdminFetch<EmailTestResult>("/api/master-admin/email/test", {
        method: "POST",
        data: { recipient, subject, body }
      });
      setMessage(result.ok ? `Test enviado con ${result.provider}` : `El proveedor ${result.provider} no pudo enviar el test.`);
    } catch (error) {
      if (error instanceof ApiError) setMessage(error.message);
      else setMessage("No se pudo enviar el test de email.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/10 backdrop-blur">
        <p className="text-xs uppercase tracking-[0.35em] text-amber-300/80">System mail</p>
        <h2 className="mt-2 text-3xl font-semibold text-white">Gmail OAuth del owner</h2>
        <p className="mt-2 text-sm text-slate-300">
          El sistema usa una conexión Gmail administrada desde este panel. No hay SMTP ni app passwords en el flujo activo.
        </p>
      </section>

      {message && <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100">{message}</div>}

      {status && (
        <section className="grid gap-4 md:grid-cols-3">
          <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Configured</p>
            <p className="mt-2 text-lg font-semibold text-white">{status.configured ? "Yes" : "No"}</p>
          </div>
          <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Account</p>
            <p className="mt-2 text-lg font-semibold text-white">{status.connected_account_email || "Not connected"}</p>
            {status.connected_account_name && <p className="mt-1 text-sm text-slate-400">{status.connected_account_name}</p>}
          </div>
          <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Status</p>
            <p className="mt-2 text-lg font-semibold text-white">{status.status}</p>
            {status.last_error && <p className="mt-1 text-sm text-rose-300">{status.last_error}</p>}
          </div>
        </section>
      )}

      <section className="flex flex-wrap gap-3">
        <button
          type="button"
          onClick={() => void startConnect()}
          disabled={loading}
          className="rounded-2xl bg-amber-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-70"
        >
          Conectar Google / Gmail
        </button>
        <button
          type="button"
          onClick={() => void disconnect()}
          disabled={loading}
          className="rounded-2xl border border-white/10 bg-white/5 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-70"
        >
          Desconectar
        </button>
      </section>

      <form onSubmit={submit} className="grid gap-6 lg:grid-cols-[1fr_1.2fr]">
        <label className="rounded-[2rem] border border-white/10 bg-slate-950/50 p-5">
          <span className="block text-sm font-medium text-slate-200">Recipient</span>
          <input
            type="email"
            required
            value={recipient}
            onChange={(event) => setRecipient(event.target.value)}
            className="mt-3 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none focus:border-amber-300/60"
            placeholder="ops@hotelchipre.com"
          />
        </label>
        <div className="space-y-4 rounded-[2rem] border border-white/10 bg-slate-950/50 p-5">
          <label className="block text-sm font-medium text-slate-200">
            <span>Subject</span>
            <input
              value={subject}
              onChange={(event) => setSubject(event.target.value)}
              className="mt-3 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none focus:border-amber-300/60"
            />
          </label>
          <label className="block text-sm font-medium text-slate-200">
            <span>Body</span>
            <textarea
              value={body}
              onChange={(event) => setBody(event.target.value)}
              rows={10}
              className="mt-3 w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none focus:border-amber-300/60"
            />
          </label>
        </div>
        <button
          type="submit"
          disabled={loading}
          className="rounded-2xl bg-amber-300 px-5 py-3 text-sm font-semibold text-slate-950 transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-70 lg:col-start-2"
        >
          {loading ? "Sending..." : "Send test email"}
        </button>
      </form>
    </div>
  );
}
