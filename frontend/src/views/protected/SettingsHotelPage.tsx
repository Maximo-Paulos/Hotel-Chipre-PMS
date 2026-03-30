export function SettingsHotelPage() {
  return (
    <div className="space-y-4">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Settings</p>
        <h1 className="text-2xl font-semibold text-slate-900">Configuración del hotel</h1>
        <p className="text-sm text-slate-600">Moneda, zona horaria, políticas, horarios y categorías.</p>
      </header>
      <div className="rounded-xl border border-dashed border-slate-300 bg-slate-50 p-6 text-sm text-slate-700">
        Pendiente: formularios con validación y guardado por hotel_id.
      </div>
    </div>
  );
}
