import { Link } from "react-router-dom";

export function ResetPasswordPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <h1 className="text-2xl font-semibold text-slate-900">Restablecer contraseña</h1>
        <p className="mb-4 text-sm text-slate-600">Ingresá tu nueva contraseña. Pediremos reautenticación para acciones sensibles.</p>
        <form className="space-y-4">
          <label className="text-sm font-medium text-slate-700">
            Nueva contraseña
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
            />
          </label>
          <label className="text-sm font-medium text-slate-700">
            Confirmar contraseña
            <input
              type="password"
              className="mt-1 w-full rounded-lg border border-slate-200 px-3 py-2 shadow-sm focus:border-brand-500 focus:ring-brand-500"
            />
          </label>
          <button className="w-full rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700">
            Guardar nueva contraseña
          </button>
        </form>
        <div className="mt-4 text-sm">
          <Link to="/login" className="text-brand-700 hover:underline">
            Volver al login
          </Link>
        </div>
      </div>
    </div>
  );
}
