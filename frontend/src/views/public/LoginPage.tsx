import { Link } from "react-router-dom";

export function LoginPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <div className="mb-6">
          <h1 className="text-2xl font-semibold text-slate-900">Ingresá a tu cuenta</h1>
          <p className="text-sm text-slate-600">Usá tu email corporativo. Logout siempre visible para cambios de turno.</p>
        </div>
        <form className="space-y-4">
          <div>
            <label className="text-sm font-medium text-slate-700">Email</label>
            <input
              type="email"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              placeholder="owner@hotel.com"
            />
          </div>
          <div>
            <label className="text-sm font-medium text-slate-700">Contraseña</label>
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
              placeholder="••••••••"
            />
          </div>
          <button
            type="submit"
            className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700"
          >
            Entrar
          </button>
        </form>
        <div className="mt-4 flex items-center justify-between text-sm">
          <Link to="/forgot-password" className="text-brand-700 hover:underline">
            Olvidé mi contraseña
          </Link>
          <Link to="/register-owner" className="text-brand-700 hover:underline">
            Crear cuenta de dueño
          </Link>
        </div>
      </div>
    </div>
  );
}
