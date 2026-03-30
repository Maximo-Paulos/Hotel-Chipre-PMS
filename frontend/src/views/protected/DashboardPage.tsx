export function DashboardPage() {
  return (
    <div className="space-y-4">
      <div>
        <p className="text-xs uppercase tracking-wide text-slate-500">Dashboard</p>
        <h1 className="text-2xl font-semibold text-slate-900">Visión general</h1>
        <p className="text-sm text-slate-600">
          Aquí mostraremos KPIs por hotel, estados de onboarding y accesos recientes (audit log).
        </p>
      </div>
      <div className="grid gap-4 md:grid-cols-3">
        {["Ocupación", "Ingresos esperados", "Pendientes de check-in"].map((card) => (
          <div key={card} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-sm text-slate-500">{card}</p>
            <div className="mt-2 text-2xl font-semibold text-slate-900">—</div>
          </div>
        ))}
      </div>
    </div>
  );
}
