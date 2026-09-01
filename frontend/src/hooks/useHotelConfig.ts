import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import { getHotelConfig, type HotelConfig } from "../api/config";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";
import i18n, { normalizeInterfaceLanguage } from "../i18n";

const hotelConfigKey = (hotelId: number | null) => ["hotel-config", hotelId];

export function useHotelConfig() {
  const { session } = useSession();
  const query = useQuery<HotelConfig>({
    queryKey: hotelConfigKey(session.hotelId),
    queryFn: () => getHotelConfig(session),
    enabled: hasValidSession(session),
    staleTime: 60 * 1000
  });

  useEffect(() => {
    if (query.data) void i18n.changeLanguage(normalizeInterfaceLanguage(query.data.interface_language));
  }, [query.data]);

  return query;
}
