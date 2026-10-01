import { useQuery } from "@tanstack/react-query";
import { useEffect } from "react";

import {
  getHotelConfig,
  getHotelInterfaceLanguage,
  type HotelConfig,
  type HotelInterfaceLanguage
} from "../api/config";
import { hasValidSession } from "../api/client";
import { useSession } from "../state/session";
import i18n, { normalizeInterfaceLanguage } from "../i18n";

import { useEffectivePermissions } from "./usePermissions";

const hotelConfigKey = (hotelId: number | null, userId: string | null) => ["hotel-config", hotelId, userId];

export function useHotelConfig() {
  const { session } = useSession();
  const { hasPermission } = useEffectivePermissions();
  const query = useQuery<HotelConfig>({
    queryKey: hotelConfigKey(session.hotelId, session.userId),
    queryFn: () => getHotelConfig(session),
    enabled: hasValidSession(session) && hasPermission("hotel_settings:read"),
    staleTime: 60 * 1000
  });

  useEffect(() => {
    if (query.data) void i18n.changeLanguage(normalizeInterfaceLanguage(query.data.interface_language));
  }, [query.data]);

  return query;
}

export function useHotelInterfaceLanguage() {
  const { session } = useSession();
  const query = useQuery<HotelInterfaceLanguage>({
    queryKey: ["hotel-interface-language", session.hotelId, session.userId],
    queryFn: () => getHotelInterfaceLanguage(session),
    enabled: hasValidSession(session),
    staleTime: 60 * 1000
  });
  const interfaceLanguage = query.data?.interface_language;

  useEffect(() => {
    if (interfaceLanguage) void i18n.changeLanguage(normalizeInterfaceLanguage(interfaceLanguage));
  }, [interfaceLanguage]);

  return query;
}
