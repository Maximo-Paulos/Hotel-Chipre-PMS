import { useState } from "react";
import { Link } from "react-router-dom";

import { useReservations } from "../hooks/useReservations";
import { useReservationDrawer } from "../hooks/useReservationDrawer";
import { reservationStatusConfig } from "../utils/reservationStatus";

function guestFullName(guest?: { first_name: string; last_name: string } | null, fallbackId?: number) {
  if (guest) return `${guest.first_name} ${guest.last_name}`.trim();
  return fallbackId ? `Huésped #${fallbackId}` : "Sin huésped";
}

// Global reservation search + quick-create access (B1). Lives in the
// AppShell header so it's reachable from every screen, not just Reservas.
export function ReservationGlobalSearch() {
  const [query, setQuery] = useState("");
  const [showResults, setShowResults] = useState(false);
  const { openReservation } = useReservationDrawer();

  const searchQuery = useReservations({ search: query });
  const results = query.trim().length >= 2 ? searchQuery.data ?? [] : [];

  const handleSelect = (id: number) => {
    openReservation(id);
    setQuery("");
    setShowResults(false);
  };

  return (
    <div className="flex items-center gap-2">
      <div className="relative">
        <input
          type="search"
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setShowResults(true);
          }}
          onFocus={() => setShowResults(true)}
          onBlur={() => window.setTimeout(() => setShowResults(false), 150)}
          placeholder="Buscar reserva por confirmación o huésped"
          aria-label="Buscar reserva"
          className="w-56 rounded-lg border border-slate-300 px-3 py-2 text-sm sm:w-72"
        />
        {showResults && query.trim().length >= 2 && (
          <div
            data-testid="reservation-search-results"
            className="absolute left-0 top-full z-30 mt-1 w-80 max-w-[90vw] rounded-lg border border-slate-200 bg-white shadow-lg"
          >
            {searchQuery.isFetching ? (
              <p className="px-3 py-2 text-sm text-slate-500">Buscando...</p>
            ) : results.length === 0 ? (
              <p className="px-3 py-2 text-sm text-slate-500">Sin reservas para "{query}".</p>
            ) : (
              <ul className="max-h-72 overflow-y-auto py-1">
                {results.slice(0, 10).map((reservation) => (
                  <li key={reservation.id}>
                    <button
                      type="button"
                      // Use onMouseDown so the click registers before the input's onBlur closes the list.
                      onMouseDown={() => handleSelect(reservation.id)}
                      className="flex w-full items-center justify-between gap-2 px-3 py-2 text-left text-sm hover:bg-slate-50"
                    >
                      <span className="min-w-0">
                        <span className="block truncate font-semibold text-slate-900">{reservation.confirmation_code}</span>
                        <span className="block truncate text-xs text-slate-500">
                          {guestFullName(reservation.guest, reservation.guest_id)}
                        </span>
                      </span>
                      <span
                        className={`shrink-0 rounded-full px-2 py-1 text-[11px] font-semibold ${reservationStatusConfig[reservation.status]?.className ?? "bg-slate-100 text-slate-800"}`}
                      >
                        {reservationStatusConfig[reservation.status]?.label ?? reservation.status}
                      </span>
                    </button>
                  </li>
                ))}
              </ul>
            )}
          </div>
        )}
      </div>
      <Link
        to="/reservas?crear=1"
        className="whitespace-nowrap rounded-lg border border-brand-200 bg-brand-50 px-3 py-2 text-sm font-semibold text-brand-700 hover:border-brand-300 hover:bg-brand-100"
      >
        Reserva rápida
      </Link>
    </div>
  );
}

export default ReservationGlobalSearch;
