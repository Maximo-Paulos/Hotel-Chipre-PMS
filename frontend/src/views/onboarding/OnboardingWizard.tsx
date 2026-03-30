import { Link, Outlet, Route, Routes } from "react-router-dom";

const steps = [
  { path: "", label: "Hotel" },
  { path: "categories", label: "Categorías" },
  { path: "rooms", label: "Habitaciones" },
  { path: "staff", label: "Staff" },
  { path: "finish", label: "Finalizar" }
];

export function OnboardingWizard() {
  return (
    <div className="rounded-2xl border border-slate-200 bg-white p-6 shadow-sm">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Onboarding obligatorio</p>
          <h1 className="text-xl font-semibold text-slate-900">Configurá tu hotel</h1>
        </div>
        <Link to="/dashboard" className="text-sm text-brand-700 hover:underline">
          Ir al dashboard
        </Link>
      </div>
      <div className="mt-4 flex flex-wrap gap-2">
        {steps.map((s, idx) => (
          <Link
            key={s.path}
            to={s.path}
            className="rounded-full border border-slate-200 px-3 py-1 text-xs font-medium text-slate-700 hover:border-brand-500 hover:text-brand-700"
          >
            {idx + 1}. {s.label}
          </Link>
        ))}
      </div>
      <div className="mt-6">
        <Routes>
          <Route index element={<StepCard title="Datos del hotel" />} />
          <Route path="categories" element={<StepCard title="Categorías" />} />
          <Route path="rooms" element={<StepCard title="Habitaciones" />} />
          <Route path="staff" element={<StepCard title="Staff inicial" />} />
          <Route path="finish" element={<StepCard title="Checklist final" />} />
        </Routes>
        <Outlet />
      </div>
    </div>
  );
}

function StepCard({ title }: { title: string }) {
  return (
    <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-slate-700">
      <h2 className="text-lg font-semibold text-slate-900">{title}</h2>
      <p className="mt-2 text-sm">Aquí irá el formulario y validación real contra /api/onboarding/*.</p>
    </div>
  );
}
