import { Link } from "react-router-dom";

export function VerifyEmailPage() {
  return (
    <div className="flex min-h-screen items-center justify-center bg-slate-50 px-4">
      <div className="w-full max-w-md rounded-2xl bg-white p-8 shadow-lg ring-1 ring-slate-100">
        <h1 className="text-2xl font-semibold text-slate-900">Verificá tu email</h1>
        <p className="mb-4 text-sm text-slate-600">
          Te enviamos un correo con un enlace de verificación. Sin email verificado no se habilitan acciones ni onboarding.
        </p>
        <div className="space-y-3 text-sm text-slate-700">
          <p>1. Revisá tu bandeja de entrada y spam.</p>
          <p>2. Si expiró, pedí reenviar el enlace.</p>
        </div>
        <div className="mt-6 flex items-center justify-between text-sm">
          <Link to="/login" className="text-brand-700 hover:underline">
            Volver al login
          </Link>
          <button className="rounded-lg border border-slate-200 px-3 py-2 text-slate-700 shadow-sm hover:bg-slate-50">
            Reenviar correo
          </button>
        </div>
      </div>
    </div>
  );
}
