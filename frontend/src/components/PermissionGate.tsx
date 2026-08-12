import type { ReactNode } from "react";
import { Navigate } from "react-router-dom";

import { useEffectivePermissions } from "../hooks/usePermissions";
import { defaultPathForRole, useSession, type Role } from "../state/session";

type PermissionGateProps = {
  children: ReactNode;
  anyPermission?: string[];
  allPermissions?: string[];
  roles?: Role[];
};

export function PermissionGate({ children, anyPermission = [], allPermissions = [], roles }: PermissionGateProps) {
  const { session } = useSession();
  const { hasAnyPermission, hasAllPermissions, permissionsKnown, isPending } = useEffectivePermissions();
  const realRole = session.baseRole ?? session.role;
  const roleAllowed = !roles || (realRole ? roles.includes(realRole) : false);
  const permissionsAllowed =
    (anyPermission.length === 0 || hasAnyPermission(anyPermission)) &&
    (allPermissions.length === 0 || hasAllPermissions(allPermissions));
  const needsPermissions = anyPermission.length > 0 || allPermissions.length > 0;

  if (roleAllowed && needsPermissions && !permissionsKnown && isPending) {
    return <p className="text-sm text-slate-500" role="status">Verificando permisos...</p>;
  }

  if (!roleAllowed || !permissionsAllowed) {
    return <Navigate to={defaultPathForRole(realRole)} replace />;
  }

  return <>{children}</>;
}
