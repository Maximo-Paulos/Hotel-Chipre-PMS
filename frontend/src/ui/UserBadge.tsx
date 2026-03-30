export function UserBadge() {
  return (
    <div className="flex items-center gap-3 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm shadow-sm">
      <div className="h-8 w-8 rounded-full bg-brand-100 text-brand-700 grid place-items-center font-semibold">OU</div>
      <div className="leading-tight">
        <div className="font-semibold text-slate-900">owner@example.com</div>
        <div className="text-xs text-slate-500">Owner • Logout</div>
      </div>
    </div>
  );
}
