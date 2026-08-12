import { useEffect, useMemo } from "react";
import { useQuery } from "@tanstack/react-query";

import { fetchEffectivePermissions, type EffectivePermissionsResponse } from "../api/permissions";
import { hasValidSession } from "../api/client";
import { normalizeRole, useSession } from "../state/session";

export const effectivePermissionsKey = (hotelId: number | null, userId: string | null) => [
  "permissions",
  "effective",
  hotelId,
  userId
];

export function useEffectivePermissions() {
  const { session, setPermissions } = useSession();
  const query = useQuery<EffectivePermissionsResponse>({
    queryKey: effectivePermissionsKey(session.hotelId, session.userId),
    queryFn: () => fetchEffectivePermissions(session),
    enabled: hasValidSession(session),
    staleTime: 30 * 1000
  });

  useEffect(() => {
    if (query.data?.hotel_id === session.hotelId) {
      setPermissions(query.data.permissions, normalizeRole(query.data.role));
    }
  }, [query.data, session.hotelId, setPermissions]);

  const permissions = useMemo(
    () => query.data?.permissions ?? session.permissions ?? [],
    [query.data?.permissions, session.permissions]
  );
  const permissionSet = useMemo(() => new Set(permissions), [permissions]);

  return {
    ...query,
    permissions,
    permissionsKnown: query.isSuccess || Array.isArray(session.permissions),
    hasPermission: (permission: string) => permissionSet.has(permission),
    hasAnyPermission: (required: string[]) => required.some((permission) => permissionSet.has(permission)),
    hasAllPermissions: (required: string[]) => required.every((permission) => permissionSet.has(permission))
  };
}
