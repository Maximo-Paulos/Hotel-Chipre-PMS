import { useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const [searchParams] = useSearchParams();
  const token = searchParams.get("token");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saved, setSaved] = useState(false);

  const handleSubmit = (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (password && password === confirm) {
      setSaved(true); // placeholder sin endpoint
      setTimeout(() => navigate("/login"), 800);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <h1 className="text-2xl font-semibold text-slate-900">Restablecer contraseÃ±a</h1>
        <p className="mb-4 text-sm text-slate-600">
          Token: {token || "pendiente"}. Al guardar redirigimos al login.
        </p>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="text-sm font-medium text-slate-700">
            Nueva contraseÃ±a
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Confirmar contraseÃ±a
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </label>
          <button className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700">
            Guardar nueva contraseÃ±a
          </button>
        </form>
        {saved && <p className="mt-3 rounded-md bg-emerald-50 p-3 text-sm text-emerald-700">ContraseÃ±a actualizada.</p>}
        <div className="mt-4 text-sm">
          <Link to="/login" className="text-brand-700 hover:underline">
            Volver al login
          </Link>
        </div>
      </div>
    </div>
  );
}
