export function HotelSelector() {
  // Placeholder; later will fetch user hotels and persist selection.
  return (
    <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm">
      <span className="inline-flex h-2 w-2 rounded-full bg-emerald-500" />
      Hotel activo: <strong className="text-slate-900">N/D</strong>
    </div>
  );
}
