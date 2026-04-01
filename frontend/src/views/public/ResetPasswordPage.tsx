import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";

import { ApiError } from "../../api/client";
import { resetPassword } from "../../api/auth";
import { useSession } from "../../state/session";

export function ResetPasswordPage() {
  const navigate = useNavigate();
  const { session, login } = useSession();
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [password, setPassword] = useState("");
  const [confirm, setConfirm] = useState("");
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  const handleSubmit = async (event: React.FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    if (!password || password !== confirm) {
      setError("Las contrasenas no coinciden.");
      return;
    }
    setLoading(true);
    try {
      const res = await resetPassword(email, code, password);
      login({
        userId: res.user.email,
        email: res.user.email,
        hotelId: session.hotelId,
        role: (res.user.role as "owner" | "receptionist") || session.role,
        accessToken: res.access_token,
        isVerified: res.user.is_verified
      });
      setSaved(true);
      setTimeout(() => navigate("/login"), 800);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Codigo invalido o expirado");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <h1 className="text-2xl font-semibold text-slate-900">Restablecer contrasena</h1>
        <p className="mb-4 text-sm text-slate-600">Ingresa el codigo que recibiste por correo.</p>
        <form className="space-y-4" onSubmit={handleSubmit}>
          <label className="text-sm font-medium text-slate-700">
            Email
            <input
              type="email"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Codigo
            <input
              type="text"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              value={code}
              onChange={(e) => setCode(e.target.value)}
              required
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Nueva contrasena
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              value={password}
              onChange={(e) => setPassword(e.target.value)}
              required
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Confirmar contrasena
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
              value={confirm}
              onChange={(e) => setConfirm(e.target.value)}
              required
            />
          </label>
          <button
            className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-60"
            disabled={loading}
          >
            {loading ? "Validando..." : "Guardar nueva contrasena"}
          </button>
        </form>
        {saved && (
          <p className="mt-3 rounded-md bg-emerald-50 p-3 text-sm text-emerald-700">
            Codigo valido. Redirigiendo al login.
          </p>
        )}
        {error && <p className="mt-3 rounded-md bg-rose-50 p-3 text-sm text-rose-700">{error}</p>}
        <div className="mt-4 text-sm">
          <Link to="/login" className="text-brand-700 hover:underline">
            Volver al login
          </Link>
        </div>
      </div>
    </div>
  );
}
