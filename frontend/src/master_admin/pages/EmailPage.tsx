import { useEffect, useState, type FormEvent } from "react";

import { ApiError } from "../../api/client";
import { masterAdminFetch } from "../api";

type EmailProvidersResponse = {
  current_provider: string;
  configured: boolean;
  available: string[];
};

export function MasterAdminEmailPage() {
  const [providers, setProviders] = useState<EmailProvidersResponse | null>(null);
  const [recipient, setRecipient] = useState("");
  const [subject, setSubject] = useState("Hotel Chipre master panel test");
  const [body, setBody] = useState("Mensaje de prueba desde el panel master.");
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState<string | null>(null);

  useEffect(() => {
    void masterAdminFetch<EmailProvidersResponse>("/api/master-admin/email/providers")
      .then(setProviders)
      .catch(() => setMessage("No se pudo leer el estado del proveedor de email."));
  }, []);

  const submit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setLoading(true);
    setMessage(null);
    try {
      const result = await masterAdminFetch<{ ok: boolean; provider: string }>("/api/master-admin/email/test", {
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
        <p className="text-xs uppercase tracking-[0.35em] text-amber-300/80">Email adapter</p>
        <h2 className="mt-2 text-3xl font-semibold text-white">Provider abstraction</h2>
        <p className="mt-2 text-sm text-slate-300">
          El facade del backend puede apuntar a SMTP hoy y a un proveedor transaccional moderno después.
        </p>
      </section>

      {message && <div className="rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-slate-100">{message}</div>}

      {providers && (
        <section className="grid gap-4 md:grid-cols-3">
          <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Current</p>
            <p className="mt-2 text-lg font-semibold text-white">{providers.current_provider}</p>
          </div>
          <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Configured</p>
            <p className="mt-2 text-lg font-semibold text-white">{providers.configured ? "Yes" : "No"}</p>
          </div>
          <div className="rounded-[1.5rem] border border-white/10 bg-slate-950/50 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Available</p>
            <p className="mt-2 text-lg font-semibold text-white">{providers.available.join(", ")}</p>
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
          {loading ? "Sending..." : "Send test email"}
        </button>
      </form>
    </div>
  );
}
