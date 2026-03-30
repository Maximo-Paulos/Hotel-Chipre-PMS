import { Link } from "react-router-dom";

export function RegisterOwnerPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-2xl rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <div className="mb-6 flex items-start justify-between">
          <div>
            <h1 className="text-2xl font-semibold text-slate-900">Crear cuenta de dueño</h1>
            <p className="text-sm text-slate-600">Pasos mínimos: email verificado + onboarding completo antes del dashboard.</p>
          </div>
          <Link to="/login" className="text-sm text-brand-700 hover:underline">
            Ya tengo cuenta
          </Link>
        </div>
        <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
          <label className="text-sm font-medium text-slate-700">
            Nombre
            <input className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500" />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Apellido
            <input className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500" />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Email corporativo
            <input className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500" />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Contraseña
            <input type="password" className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500" />
          </label>
        </div>
        <button className="mt-6 w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700">
          Crear cuenta y verificar email
        </button>
      </div>
    </div>
  );
}
