import { useQuery } from "@tanstack/react-query";

import { getHotelConfig, type HotelConfig } from "../api/config";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";

const hotelConfigKey = (hotelId: number | null) => ["hotel-config", hotelId];

export function useHotelConfig() {
  const { session } = useSession();
  return useQuery<HotelConfig>({
    queryKey: hotelConfigKey(session.hotelId),
    queryFn: () => getHotelConfig(session),
    enabled: hasValidSession(session),
    staleTime: 60 * 1000
  });
}
