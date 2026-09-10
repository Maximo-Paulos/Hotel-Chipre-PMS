import { useId, useState, type FormEvent } from "react";

import { submitLead } from "../../api/marketing";
import { PUBLIC_CTA_MODE, resolveAppUrl } from "../../config/publicUrls";

type EarlyAccessFormProps = {
  /** Where on the page this was submitted from, so leads can be attributed. */
  source: string;
  tone?: "light" | "dark";
  className?: string;
};

type Status = "idle" | "sending" | "done" | "error" | "rate-limited";

const MESSAGES: Record<Exclude<Status, "idle" | "sending">, string> = {
  done: "Listo. Te escribimos a esa dirección cuando abramos la próxima tanda.",
  error: "No pudimos guardar tu mail. Probá de nuevo en un momento.",
  "rate-limited": "Ya recibimos varios intentos desde acá. Esperá unos minutos y probá otra vez."
};

/**
 * Captures interest while access is invitation-only.
 *
 * When VITE_PUBLIC_CTA_MODE flips to "register" this renders a link to
 * self-serve signup instead, so reopening registration is an env change rather
 * than a rewrite of every call to action.
 */
export function EarlyAccessForm({ source, tone = "dark", className = "" }: EarlyAccessFormProps) {
  const emailId = useId();
  const [email, setEmail] = useState("");
  const [hotel, setHotel] = useState("");
  const [honeypot, setHoneypot] = useState("");
  const [status, setStatus] = useState<Status>("idle");

  const light = tone === "light";

  if (PUBLIC_CTA_MODE === "register") {
    return (
      <a
        href={resolveAppUrl("/register-owner")}
        className={`inline-flex min-h-[3.25rem] items-center justify-center rounded-control bg-brass-500 px-6 text-base font-medium text-ink-950 transition duration-200 ease-rack hover:bg-brass-400 ${className}`.trim()}
      >
        Crear la cuenta del hotel
      </a>
    );
  }

  async function handleSubmit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (status === "sending") return;
    setStatus("sending");
    try {
      await submitLead({
        email: email.trim(),
        hotel_name: hotel.trim() || undefined,
        source,
        // Sent as a normal field; the server treats anything here as a bot.
        company_website: honeypot || undefined
      });
      setStatus("done");
      setEmail("");
      setHotel("");
    } catch (error) {
      setStatus((error as Error).message === "rate_limited" ? "rate-limited" : "error");
    }
  }

  if (status === "done") {
    return (
      <p
        role="status"
        className={`rounded-control px-4 py-4 text-sm leading-6 ${
          light ? "bg-white/10 text-white" : "bg-brand-50 text-brand-800"
        } ${className}`.trim()}
      >
        {MESSAGES.done}
      </p>
    );
  }

  const fieldClasses = light
    ? "w-full min-h-[3.25rem] rounded-control border border-white/15 bg-white/[0.06] px-4 text-base text-white placeholder:text-ink-400"
    : "w-full min-h-[3.25rem] rounded-control border border-ink-200 bg-white px-4 text-base text-ink-900 placeholder:text-ink-400";

  return (
    <form onSubmit={handleSubmit} className={`w-full ${className}`.trim()} noValidate={false}>
      <div className="flex flex-col gap-2.5 sm:flex-row">
        <div className="flex-1">
          <label htmlFor={emailId} className="sr-only">
            Tu correo
          </label>
          <input
            id={emailId}
            type="email"
            required
            autoComplete="email"
            inputMode="email"
            value={email}
            onChange={(event) => setEmail(event.target.value)}
            placeholder="tu@hotel.com"
            className={fieldClasses}
          />
        </div>
        <button
          type="submit"
          disabled={status === "sending"}
          className="min-h-[3.25rem] shrink-0 rounded-control bg-brass-500 px-6 text-base font-medium text-ink-950 transition duration-200 ease-rack hover:bg-brass-400 disabled:opacity-60"
        >
          {status === "sending" ? "Enviando…" : "Pedir acceso"}
        </button>
      </div>

      <label className="mt-2.5 block">
        <span className="sr-only">Nombre del hotel</span>
        <input
          type="text"
          autoComplete="organization"
          value={hotel}
          onChange={(event) => setHotel(event.target.value)}
          placeholder="Nombre del hotel (opcional)"
          className={fieldClasses}
        />
      </label>

      {/* Honeypot: off-screen rather than display:none, which some bots skip.
          Never announced to assistive tech and never focusable by keyboard. */}
      <div aria-hidden="true" className="absolute left-[-9999px] top-auto h-px w-px overflow-hidden">
        <label>
          Sitio web
          <input
            type="text"
            tabIndex={-1}
            autoComplete="off"
            value={honeypot}
            onChange={(event) => setHoneypot(event.target.value)}
          />
        </label>
      </div>

      {status === "error" || status === "rate-limited" ? (
        <p role="alert" className={`mt-3 text-sm ${light ? "text-brass-300" : "text-brass-700"}`}>
          {MESSAGES[status]}
        </p>
      ) : null}
    </form>
  );
}

export default EarlyAccessForm;
