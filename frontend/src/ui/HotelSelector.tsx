import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { getHotelConfig } from "../api/config";
import { safeHotelId, useSession } from "../state/session";

type HotelOption = { id: number; hotel_name?: string };

export function HotelSelector() {
  const queryClient = useQueryClient();
  const { session, setHotelId } = useSession();
  const [value, setValue] = useState(String(session.hotelId));

  useEffect(() => {
    setValue(String(session.hotelId));
  }, [session.hotelId]);

  const { data: hotels, isLoading } = useQuery<HotelOption[]>({
    queryKey: ["hotels-list"],
    queryFn: async () => {
      // No hay endpoint dedicado; usamos el config actual como único hotel si falla
      try {
        const cfg = await getHotelConfig(session);
        return [{ id: cfg.id, hotel_name: cfg.hotel_name }];
      } catch {
        return [{ id: 1, hotel_name: "Hotel activo" }];
      }
    },
    staleTime: 5 * 60 * 1000
  });

  const options = useMemo(() => hotels ?? [{ id: 1, hotel_name: "Hotel activo" }], [hotels]);

  const apply = () => {
    const next = safeHotelId(value);
    setHotelId(next);
    queryClient.invalidateQueries(); // refresca caches con hotel nuevo
  };

  return (
    <div className="flex items-center gap-2 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-sm text-slate-700 shadow-sm">
      <select
        aria-label="Hotel activo"
        className="rounded-md border border-slate-200 px-2 py-1 text-sm focus:border-brand-500 focus:outline-none focus:ring-1 focus:ring-brand-500"
        value={value}
        onChange={(e) => setValue(e.target.value)}
        onBlur={apply}
        disabled={isLoading}
      >
        {options.map((opt) => (
          <option key={opt.id} value={opt.id}>
            {opt.hotel_name ? `${opt.hotel_name} (ID ${opt.id})` : `Hotel ${opt.id}`}
          </option>
        ))}
      </select>
      <button
        type="button"
        className="text-brand-700 underline decoration-dotted decoration-2 underline-offset-2"
        onClick={apply}
        disabled={isLoading}
      >
        Aplicar
      </button>
      <span className="text-xs text-emerald-700">ID {safeHotelId(value)}</span>
    </div>
  );
}
