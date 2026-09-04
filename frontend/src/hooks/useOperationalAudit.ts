import { useQuery } from "@tanstack/react-query";

import { hasValidSession } from "../api/client";
import { getOperationalAudit, type OperationalAuditFilters, type OperationalAuditResponse } from "../api/operationalAudit";
import { useSession } from "../state/session";

export function useOperationalAudit(filters: OperationalAuditFilters = {}, enabled = true) {
  const { session } = useSession();
  return useQuery<OperationalAuditResponse>({
    queryKey: ["operational-audit", session.hotelId, filters],
    queryFn: () => getOperationalAudit(filters, session),
    enabled: enabled && hasValidSession(session),
    staleTime: 10 * 1000
  });
}
