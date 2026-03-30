import { useState } from "react";
import { Link } from "react-router-dom";

export function ForgotPasswordPage() {
  const [email, setEmail] = useState("");
  const [sent, setSent] = useState(false);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSent(true); // No endpoint yet; keep flow non bloqueante
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <h1 className="text-2xl font-semibold text-slate-900">Recuperar acceso</h1>
        <p className="mb-4 text-sm text-slate-600">Enviaremos un enlace seguro a tu correo.</p>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="text-sm font-medium text-slate-700">
            Email
            <input
              type="email"
              required
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              placeholder="tu@hotel.com"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
          </label>
          <button className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700">
            Enviar enlace
          </button>
        </form>
        {sent && <p className="mt-3 rounded-md bg-emerald-50 p-3 text-sm text-emerald-700">Si el email existe, se enviÃ³ un enlace.</p>}
        <div className="mt-4 text-sm">
          <Link to="/login" className="text-brand-700 hover:underline">
            Volver al login
          </Link>
        </div>
      </div>
    </div>
  );
}
