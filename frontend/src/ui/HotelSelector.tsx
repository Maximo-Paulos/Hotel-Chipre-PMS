import { useEffect, useState } from "react";

import { safeHotelId, useSession } from "../state/session";

export function HotelSelector() {
  const { session, setHotelId } = useSession();
  const [value, setValue] = useState(String(session.hotelId));

  useEffect(() => {
    setValue(String(session.hotelId));
  }, [session.hotelId]);

  const apply = () => setHotelId(safeHotelId(value));
  const fallback = safeHotelId(value) === 1 && session.userId === "guest";

  return (
    <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm">
      <input
        aria-label="Hotel ID"
        className="w-16 rounded-md border border-slate-200 px-2 py-1 text-center text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={apply}
      />
      <button
        type="button"
        className="text-brand-700 underline decoration-dotted decoration-2 underline-offset-2"
        onClick={apply}
      >
        Hotel activo
      </button>
      {fallback ? (
        <span className="text-xs text-amber-700">Fallback seguro</span>
      ) : (
        <span className="text-xs text-emerald-700">ID {safeHotelId(value)}</span>
      )}
    </div>
  );
}
