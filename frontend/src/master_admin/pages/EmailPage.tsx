import { useCallback, useEffect, useState, type FormEvent } from "react";

import { ApiError } from "../../api/client";
import { masterAdminFetch, type MasterEmailStatus } from "../api";

type EmailTestResult = {
  ok: boolean;
  provider: string;
  sender_email?: string | null;
  reply_to?: string | null;
  provider_message_id?: string | null;
};

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

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setMessage(null);
    try {
      const result = await masterAdminFetch<EmailTestResult>("/api/master-admin/email/test", {
        method: "POST",
        data: { recipient, subject, body }
      });
      setMessage(
        result.ok
          ? `Test enviado con ${result.provider}${result.provider_message_id ? ` (${result.provider_message_id})` : ""}.`
          : `El provider ${result.provider} no pudo enviar el test.`
      );
      await reloadStatus();
    } catch (error) {
      if (error instanceof ApiError) setMessage(error.message);
      else setMessage("No se pudo enviar el test de email.");
    } finally {
      setLoading(false);
    }
  };

  const statusLabel = status?.configured ? "Activo" : "Inactivo";

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/10 backdrop-blur">
        <p className="text-xs uppercase tracking-[0.35em] text-amber-300/80">System mail</p>
        <h2 className="mt-2 text-3xl font-semibold text-white">Resend como provider activo</h2>
        <p className="mt-2 text-sm text-slate-300">
          El sistema de mails transaccionales usa exclusivamente Resend. No hay OAuth de Gmail ni SMTP en el flujo
          activo del panel.
        </p>
      </section>

      {message && <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100">{message}</div>}

      {status && (
        <section className="grid gap-4 md:grid-cols-4">
          <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Provider</p>
            <p className="mt-2 text-lg font-semibold text-white">{status.provider}</p>
          </div>
          <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Sender</p>
            <p className="mt-2 text-lg font-semibold text-white">{status.sender_email || "Not set"}</p>
            {status.connected_account_name && <p className="mt-1 text-sm text-slate-400">{status.connected_account_name}</p>}
          </div>
          <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Reply-to</p>
            <p className="mt-2 text-lg font-semibold text-white">{status.reply_to || "Not set"}</p>
          </div>
          <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Status</p>
            <p className="mt-2 text-lg font-semibold text-white">{statusLabel}</p>
            {status.last_error && <p className="mt-1 text-sm text-rose-300">{status.last_error}</p>}
          </div>
        </section>
      )}

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
          {loading ? "Sending..." : "Send test mail"}
        </button>
      </form>
    </div>
  );
}
