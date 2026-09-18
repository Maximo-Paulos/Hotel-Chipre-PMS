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
  const shouldLoadHotelNames = session.baseRole !== "housekeeping";

  useEffect(() => {
    setValue(session.hotelId ? String(session.hotelId) : "");
  }, [session.hotelId]);

  const { data: hotels, isLoading } = useQuery<HotelOption[]>({
    queryKey: ["hotels-list", session.hotelIds?.join(",") || session.hotelId || "none"],
    enabled: hasValidSession(session) && shouldLoadHotelNames,
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
      <div className="rounded-control border border-dashed border-slate-200 bg-white px-3 py-2 text-sm text-slate-500 shadow-sm">
        Iniciá sesión para elegir un hotel activo.
      </div>
    );
  }

  // A picker with one option is not a choice. Most accounts run a single
  // hotel, and for them this control used to spend a select, an "Aplicar"
  // link and an "ID 1" label on every screen to show a value that can never
  // change. The active hotel's name is in the sidebar header instead.
  if (options.length <= 1) return null;

  return (
    <div className="flex w-full min-w-0 max-w-full items-center gap-1 overflow-hidden rounded-control border border-slate-200 bg-white py-1 pl-1 pr-2 text-sm text-slate-700 shadow-sm sm:w-auto">
      <select
        aria-label="Hotel activo"
        className="h-11 min-w-0 max-w-full flex-1 rounded-md border-0 bg-transparent px-2 py-1 text-sm font-medium text-slate-900 focus:outline-none focus:ring-2 focus:ring-brand-500 sm:flex-none md:h-9"
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
        className="inline-flex min-h-11 items-center rounded-md px-2 text-sm font-medium text-brand-700 hover:bg-brand-50 active:scale-[0.98] disabled:opacity-50 md:min-h-9"
        onClick={apply}
        disabled={isLoading}
      >
        Aplicar
      </button>
    </div>
  );
}
