import { useMutation, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import { advanceBusinessClock } from "../../api/config";
import { hasValidSession } from "../../api/client";
import { queryKeys } from "../../api/queryKeys";
import { queryBelongsToHotel } from "../../api/queryInvalidation";
import { useBusinessClock } from "../../hooks/useBusinessClock";
import { useSession } from "../../state/session";

type LocalBusinessClockCardProps = {
  ownerOnly: boolean;
};

const formatBusinessDate = (value: string) => {
  const match = /^(\d{4})-(\d{2})-(\d{2})$/.exec(value);
  return match ? `${match[3]}/${match[2]}/${match[1]}` : value;
};

export function LocalBusinessClockCard({ ownerOnly }: LocalBusinessClockCardProps) {
  const { session } = useSession();
  const queryClient = useQueryClient();
  const [error, setError] = useState<string | null>(null);
  const hotelId = session.hotelId;
  const queryKey = queryKeys.businessClock(hotelId);
  const localOwner = import.meta.env.DEV && ownerOnly && hasValidSession(session);
  const clockQuery = useBusinessClock({ enabled: localOwner });

  const advanceMutation = useMutation({
    mutationFn: () => advanceBusinessClock(session),
    onSuccess: async (clock) => {
      setError(null);
      queryClient.setQueryData(queryKey, clock);
      await queryClient.invalidateQueries({
        predicate: (query) => queryBelongsToHotel(query.queryKey, hotelId ?? 0)
      }, { throwOnError: false });
    },
    onError: () => setError("No se pudo avanzar la fecha de negocio. Revisá la conexión local y volvé a intentar.")
  });

  if (!localOwner || (clockQuery.data && !clockQuery.data.simulation_enabled)) return null;

  const advanceDay = () => {
    setError(null);
    advanceMutation.mutate();
  };

  return (
    <section
      aria-labelledby="local-business-clock-title"
      className="space-y-3 rounded-xl border border-amber-200 bg-amber-50 p-4 shadow-sm"
      data-testid="local-business-clock"
    >
      <div>
        <p className="text-xs font-semibold uppercase tracking-wide text-amber-800">Solo desarrollo local</p>
        <h2 id="local-business-clock-title" className="mt-1 text-lg font-semibold text-slate-900">
          Reloj de negocio
        </h2>
        <p className="mt-1 text-sm text-slate-700">
          Avanza la fecha operativa de este hotel en la base local. La hora real del equipo no cambia.
        </p>
      </div>

      {clockQuery.isLoading ? (
        <p className="text-sm text-slate-600">Leyendo la fecha operativa local...</p>
      ) : clockQuery.isError ? (
        <p className="text-sm text-rose-700">No se pudo leer el reloj local. Revisá que el backend use la base PostgreSQL de simulación.</p>
      ) : clockQuery.data?.simulation_enabled ? (
        <div className="flex flex-wrap items-center justify-between gap-3">
          <p className="text-sm font-medium text-slate-800">
            Fecha operativa: <span data-testid="local-business-clock-date">{formatBusinessDate(clockQuery.data.business_date)}</span>
          </p>
          <button
            type="button"
            onClick={advanceDay}
            disabled={advanceMutation.isPending}
            className="rounded-lg bg-amber-700 px-4 py-2 text-sm font-semibold text-white hover:bg-amber-800 disabled:cursor-not-allowed disabled:opacity-60"
            data-testid="advance-local-business-day"
          >
            {advanceMutation.isPending ? "Avanzando..." : "Cerrar día y avanzar"}
          </button>
        </div>
      ) : null}

      {advanceMutation.isSuccess && clockQuery.data?.simulation_enabled && (
        <p role="status" className="text-sm font-medium text-emerald-800">
          Fecha actualizada al {formatBusinessDate(clockQuery.data.business_date)}.
        </p>
      )}
      {error && <p role="alert" className="text-sm text-rose-700">{error}</p>}
    </section>
  );
}
