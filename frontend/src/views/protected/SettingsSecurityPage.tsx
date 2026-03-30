export function SettingsSecurityPage() {
  return (
    <div className="space-y-4">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Settings</p>
        <h1 className="text-2xl font-semibold text-slate-900">Seguridad</h1>
        <p className="text-sm text-slate-600">Políticas de sesión, timeouts, reautenticación y auditoría.</p>
      </header>
      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-700">
        Pendiente: controles de tiempo de sesión, logout global, auditoría de acciones sensibles.
      </div>
    </div>
  );
}
