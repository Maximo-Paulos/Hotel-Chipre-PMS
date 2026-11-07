export type ReservationDepartureStatsInput = {
  check_out_date: string;
  status: string;
};

/** Counts scheduled departures for the selected business date. */
export function countScheduledDepartures(
  reservations: readonly ReservationDepartureStatsInput[],
  today: string
): number {
  return reservations.filter(
    (reservation) =>
      reservation.status !== "cancelled" &&
      reservation.status !== "no_show" &&
      reservation.check_out_date === today
  ).length;
}
