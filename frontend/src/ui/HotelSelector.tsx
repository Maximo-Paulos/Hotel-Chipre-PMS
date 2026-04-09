import { useEffect, useMemo, useState } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";

import { getHotelConfig } from "../api/config";
import { safeHotelId, useSession } from "../state/session";
import { hasValidSession } from "../api/client";

type HotelOption = { id: number; hotel_name?: string };

export function HotelSelector() {
  const queryClient = useQueryClient();
  const { session, setHotelId } = useSession();
  const [value, setValue] = useState(session.hotelId ? String(session.hotelId) : "");

  useEffect(() => {
    setValue(session.hotelId ? String(session.hotelId) : "");
  }, [session.hotelId]);

  const { data: hotels, isLoading } = useQuery<HotelOption[]>({
    queryKey: ["hotels-list", session.hotelIds?.join(",") || session.hotelId || "none"],
    enabled: hasValidSession(session),
    queryFn: async () => {
      const ids = session.hotelIds?.length ? session.hotelIds : session.hotelId ? [session.hotelId] : [];
      const results: HotelOption[] = [];
      for (const id of ids) {
        try {
          const cfg = await getHotelConfig({ ...session, hotelId: id });
          results.push({ id, hotel_name: cfg.hotel_name });
        } catch {
          results.push({ id });
        }
      }
      return results;
    },
    staleTime: 5 * 60 * 1000
  });

  const options = useMemo(() => {
    if (hotels?.length) return hotels;
    const ids = session.hotelIds?.length ? session.hotelIds : session.hotelId ? [safeHotelId(session.hotelId)] : [];
    return ids.filter((id): id is number => typeof id === "number").map((id) => ({ id, hotel_name: "Hotel activo" }));
  }, [hotels, session.hotelId, session.hotelIds]);

  const apply = () => {
    const next = safeHotelId(value);
    if (!next) return;
    setHotelId(next);
    queryClient.invalidateQueries();
  };

  if (!hasValidSession(session)) {
    return (
      <div className="rounded-lg border border-dashed border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 shadow-sm">
        Iniciá sesión para elegir un hotel activo.
      </div>
    );
  }

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
        <option value="" disabled>
          Seleccioná un hotel
        </option>
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
      <span className="text-xs text-emerald-700">ID {safeHotelId(value) ?? "—"}</span>
    </div>
  );
}
