import type { ReactNode } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";

import { useEffectivePermissions } from "../hooks/usePermissions";
import { defaultPathForRole, useSession, type Role } from "../state/session";

type PermissionGateProps = {
  children: ReactNode;
  anyPermission?: string[];
  allPermissions?: string[];
  roles?: Role[];
};

export function PermissionGate({ children, anyPermission = [], allPermissions = [], roles }: PermissionGateProps) {
  const { t } = useTranslation("appshell");
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
    return (
      <section className="mx-auto max-w-2xl rounded-xl border border-amber-200 bg-amber-50 p-6 text-amber-950" role="alert" data-testid="permission-denied-page">
        <h1 className="text-lg font-semibold">{t("accessDenied.title")}</h1>
        <p className="mt-2 text-sm">{t("accessDenied.description")}</p>
        <Link className="mt-4 inline-flex rounded-lg border border-amber-300 bg-white px-3 py-2 text-sm font-semibold text-amber-950 hover:bg-amber-100" to={defaultPathForRole(realRole)}>
          {t("accessDenied.home")}
        </Link>
      </section>
    );
  }

  return <>{children}</>;
}
