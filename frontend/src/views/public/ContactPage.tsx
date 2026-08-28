import { useState, type FormEvent, type ReactNode } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { submitPublicInquiry } from "../../api/publicInquiries";
import { Seo } from "../../components/Seo";
import { MarketingIcon } from "../../components/marketing/MarketingIcon";
import { MarketingShell } from "../../components/marketing/MarketingShell";
import { ALLOW_INDEXING } from "../../config/publicUrls";

type ContactForm = {
  name: string;
  email: string;
  company_name: string;
  phone: string;
  message: string;
  privacy_consent: boolean;
  website: string;
};

const initialForm: ContactForm = {
  name: "",
  email: "",
  company_name: "",
  phone: "",
  message: "",
  privacy_consent: false,
  website: ""
};

export function ContactPage() {
  const navigate = useNavigate();
  const [form, setForm] = useState<ContactForm>(initialForm);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const updateField = <K extends keyof ContactForm>(field: K, value: ContactForm[K]) => {
    setForm((current) => ({ ...current, [field]: value }));
  };

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setIsSubmitting(true);
    try {
      await submitPublicInquiry({
        name: form.name,
        email: form.email,
        company_name: form.company_name || undefined,
        phone: form.phone || undefined,
        message: form.message,
        source_path: typeof window === "undefined" ? "/contacto" : window.location.pathname,
        privacy_consent: form.privacy_consent,
        website: form.website
      });
      if (typeof window !== "undefined") {
        window.sessionStorage.setItem("hotel-chipre:public-inquiry-accepted", "1");
      }
      navigate("/gracias", { replace: true });
    } catch (requestError) {
      if (requestError instanceof ApiError && requestError.status === 429) {
        setError("Recibimos demasiadas consultas desde este origen. Intentá nuevamente más tarde.");
      } else {
        setError("No pudimos enviar tu consulta. Revisá los datos e intentá nuevamente.");
      }
    } finally {
      setIsSubmitting(false);
    }
  };

  return (
    <MarketingShell>
      <Seo
        title="Contacto | Consultas sobre Hotel Chipre PMS"
        description="Enviá una consulta sobre Hotel Chipre PMS y contanos qué necesitás ordenar en la operación de tu hotel."
        canonicalPath="/contacto"
        noindex={!ALLOW_INDEXING}
        breadcrumbLabel="Contacto"
      />
      <section className="mx-auto grid max-w-6xl gap-10 px-4 py-12 sm:px-6 sm:py-16 lg:grid-cols-[0.8fr_1.2fr] lg:px-8">
        <div className="space-y-6">
          <div className="space-y-4">
            <p className="text-xs font-semibold uppercase tracking-[0.2em] text-brand-700">Contacto</p>
            <h1 className="text-4xl font-semibold tracking-tight text-slate-950">Contanos qué necesitás para ordenar tu hotel</h1>
            <p className="text-lg leading-8 text-slate-700">
              Dejanos tu consulta y el equipo comercial la va a revisar. Los campos opcionales pueden quedar en blanco.
            </p>
          </div>

          <div className="space-y-4 rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm">
            <div className="flex gap-3">
              <MarketingIcon name="shield" className="mt-0.5 shrink-0 text-brand-700" />
              <div>
                <h2 className="font-semibold text-slate-950">Tus datos quedan asociados a esta consulta</h2>
                <p className="mt-1 text-sm leading-6 text-slate-600">
                  Usamos la información para responderte y gestionar el contacto comercial. Consultá la{" "}
                  <Link to="/privacy" className="text-brand-700 underline underline-offset-2">Política de Privacidad</Link>.
                </p>
              </div>
            </div>
            <div className="flex gap-3">
              <MarketingIcon name="message" className="mt-0.5 shrink-0 text-brand-700" />
              <p className="text-sm leading-6 text-slate-600">Si todavía estás explorando, también podés revisar las <Link to="/faq" className="text-brand-700 underline underline-offset-2">preguntas frecuentes</Link>.</p>
            </div>
          </div>
        </div>

        <form onSubmit={handleSubmit} className="rounded-[2rem] border border-slate-200 bg-white p-6 shadow-sm sm:p-8">
          <div className="grid gap-5 sm:grid-cols-2">
            <Field label="Nombre" htmlFor="inquiry-name" required>
              <input id="inquiry-name" name="name" required maxLength={120} value={form.name} onChange={(event) => updateField("name", event.target.value)} autoComplete="name" className={inputClasses} />
            </Field>
            <Field label="Email" htmlFor="inquiry-email" required>
              <input id="inquiry-email" name="email" type="email" required maxLength={320} value={form.email} onChange={(event) => updateField("email", event.target.value)} autoComplete="email" className={inputClasses} />
            </Field>
            <Field label="Empresa" htmlFor="inquiry-company">
              <input id="inquiry-company" name="company_name" maxLength={160} value={form.company_name} onChange={(event) => updateField("company_name", event.target.value)} autoComplete="organization" className={inputClasses} />
            </Field>
            <Field label="Teléfono" htmlFor="inquiry-phone">
              <input id="inquiry-phone" name="phone" type="tel" maxLength={50} value={form.phone} onChange={(event) => updateField("phone", event.target.value)} autoComplete="tel" className={inputClasses} />
            </Field>
          </div>

          <Field label="Mensaje" htmlFor="inquiry-message" required className="mt-5">
            <textarea id="inquiry-message" name="message" required minLength={1} maxLength={4000} value={form.message} onChange={(event) => updateField("message", event.target.value)} rows={7} className={inputClasses} />
          </Field>

          <label htmlFor="inquiry-privacy" className="mt-5 flex items-start gap-3 text-sm leading-6 text-slate-700">
            <input id="inquiry-privacy" name="privacy_consent" type="checkbox" required checked={form.privacy_consent} onChange={(event) => updateField("privacy_consent", event.target.checked)} className="mt-1 h-4 w-4 rounded border-slate-300 text-brand-600 focus:ring-brand-500" />
            <span>Acepto la <Link to="/privacy" className="text-brand-700 underline underline-offset-2">Política de Privacidad</Link> y autorizo el uso de estos datos para responder mi consulta.</span>
          </label>

          <div aria-hidden="true" className="absolute -left-[10000px] h-px w-px overflow-hidden">
            <label htmlFor="inquiry-website">Website</label>
            <input id="inquiry-website" name="website" tabIndex={-1} autoComplete="off" value={form.website} onChange={(event) => updateField("website", event.target.value)} />
          </div>

          {error ? <p role="alert" className="mt-5 rounded-2xl border border-rose-200 bg-rose-50 p-4 text-sm leading-6 text-rose-800">{error}</p> : null}

          <button type="submit" disabled={isSubmitting} className="mt-6 inline-flex min-h-12 w-full items-center justify-center gap-2 rounded-full bg-brand-600 px-5 py-3 text-sm font-semibold text-white shadow-sm transition hover:bg-brand-700 focus:outline-none focus:ring-2 focus:ring-brand-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60">
            <MarketingIcon name="arrow-right" size={18} />
            {isSubmitting ? "Enviando consulta…" : "Enviar consulta"}
          </button>
          <p className="mt-3 text-center text-xs leading-5 text-slate-500">Al enviar, la consulta se registra y se intenta notificar al destinatario comercial configurado.</p>
        </form>
      </section>
    </MarketingShell>
  );
}

const inputClasses = "mt-2 block w-full rounded-2xl border border-slate-300 bg-white px-4 py-3 text-sm text-slate-900 outline-none transition placeholder:text-slate-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200";

function Field({ label, htmlFor, required = false, className = "", children }: { label: string; htmlFor: string; required?: boolean; className?: string; children: ReactNode }) {
  return <label htmlFor={htmlFor} className={`block text-sm font-medium text-slate-800 ${className}`}>
    {label}{required ? <span aria-hidden="true"> *</span> : null}
    {children}
  </label>;
}
