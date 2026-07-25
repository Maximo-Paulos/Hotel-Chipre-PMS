import { useSearchParams } from "react-router-dom";

// B1: the reservation drawer is controlled entirely by the `?reserva=<id>`
// query param on whatever page is currently mounted, so it's linkable,
// survives reload, and needs no new global state. Every trigger (header
// search, dashboard, guest history, ...) shares this hook instead of each
// reimplementing the same searchParams read/write.
export function useReservationDrawer() {
  const [searchParams, setSearchParams] = useSearchParams();

  const raw = searchParams.get("reserva");
  const parsed = raw ? Number(raw) : NaN;
  const reservationId = Number.isFinite(parsed) && parsed > 0 ? parsed : null;

  const openReservation = (id: number) => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.set("reserva", String(id));
      return next;
    });
  };

  const closeReservation = () => {
    setSearchParams((prev) => {
      const next = new URLSearchParams(prev);
      next.delete("reserva");
      return next;
    });
  };

  return { reservationId, openReservation, closeReservation };
}
