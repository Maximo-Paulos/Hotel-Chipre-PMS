import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";

import {
  fetchPermissionMatrix,
  updatePermissionOverride,
  type PermissionRole,
  type PermissionMatrixResponse,
  type PermissionOverridePayload
} from "../../api/permissions";
import { hasValidSession } from "../../api/client";
import { useSession } from "../../state/session";

const roleOrder: PermissionRole[] = ["owner", "co_owner", "manager", "receptionist", "housekeeping"];

const roleLabels: Record<PermissionRole, string> = {
  owner: "Owner",
  co_owner: "Co-owner",
  manager: "Manager",
  receptionist: "Recepcion",
  housekeeping: "Housekeeping"
};

const permissionLabels: Record<string, string> = {
  "config:manage": "Configurar hotel",
  "permissions:manage": "Administrar permisos",
  "guest:edit": "Editar huespedes",
  "guest:tags": "Etiquetas de huesped",
  "reservation:create": "Crear reservas",
  "reservation:room_move": "Mover reservas",
  "checkin:perform": "Check-in",
  "room:block": "Bloquear habitaciones",
  "company:manage": "Companies",
  "cash:operate": "Operar caja",
  "cash:approve_difference": "Aprobar diferencias",
  "stock:operate": "Operar inventario",
  "stock:adjust": "Autorizar ajustes de inventario",
  "checkin:override_prohibido": "Override prohibido alojar",
  "reports:view": "Ver reportes",
  "apikey:manage": "Administrar API Keys"
};

const getPermissionCodes = (data?: PermissionMatrixResponse) => {
  const firstRole = roleOrder.find((role) => data?.matrix?.[role]);
  return firstRole ? Object.keys(data?.matrix[firstRole] || {}) : [];
};

export function SettingsPermissionsPage() {
  const { session } = useSession();
  const qc = useQueryClient();
  // C4: reads baseRole -- this gates both the permission-matrix fetch and
  // its edit UI, the most security-sensitive page in the app. Must reflect
  // the real user, not the "Cambiar vista" preview role.
  const canManage = ["owner", "co_owner"].includes(session.baseRole ?? "");

  const matrixQuery = useQuery({
    queryKey: ["permissions-matrix", session.hotelId],
    enabled: hasValidSession(session) && canManage,
    queryFn: () => fetchPermissionMatrix(session)
  });
  const overrideMutation = useMutation({
    mutationFn: (payload: PermissionOverridePayload) => updatePermissionOverride(payload, session),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["permissions-matrix", session.hotelId] })
  });

  if (!hasValidSession(session)) {
    return <p className="text-sm text-slate-600">Inicia sesion con un hotel activo para editar permisos.</p>;
  }
  if (!canManage) {
    return <p className="text-sm text-slate-600">Solo owner y co-owner pueden editar permisos.</p>;
  }

  const permissionCodes = getPermissionCodes(matrixQuery.data);

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Settings</p>
        <h1 className="text-2xl font-semibold text-slate-900">Permisos</h1>
        <p className="text-sm text-slate-600">
          Ajusta permisos por rol para este hotel. Cada cambio guarda un override auditable sobre la matriz base.
        </p>
      </header>

      <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 text-sm text-amber-900 shadow-sm">
        Los roles owner y co-owner tienen permisos criticos. Cambia esta matriz solo si el flujo operativo del hotel lo
        requiere.
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-800">Matriz por rol</h2>
          {matrixQuery.isFetching && <span className="text-xs text-slate-500">Actualizando...</span>}
        </div>

        {matrixQuery.isLoading ? (
          <p className="mt-3 text-sm text-slate-600">Cargando permisos...</p>
        ) : (
          <div className="mt-3 overflow-x-auto">
            <table className="min-w-full divide-y divide-slate-200 text-sm">
              <thead className="bg-slate-50">
                <tr>
                  <th className="sticky left-0 bg-slate-50 px-3 py-2 text-left font-semibold text-slate-600">
                    Permiso
                  </th>
                  {roleOrder.map((role) => (
                    <th key={role} className="px-3 py-2 text-center font-semibold text-slate-600">
                      {roleLabels[role]}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-200">
                {permissionCodes.map((code) => {
                  const description =
                    matrixQuery.data?.matrix.owner?.[code]?.description ||
                    matrixQuery.data?.matrix.co_owner?.[code]?.description ||
                    code;
                  return (
                    <tr key={code}>
                      <td className="sticky left-0 bg-white px-3 py-2">
                        <p className="font-medium text-slate-800">{permissionLabels[code] || code}</p>
                        <p className="text-xs text-slate-500">{description}</p>
                        <code className="text-[11px] text-slate-400">{code}</code>
                      </td>
                      {roleOrder.map((role) => {
                        const cell = matrixQuery.data?.matrix[role]?.[code];
                        const checked = Boolean(cell?.allowed);
                        const isOverride = cell?.source === "override";
                        return (
                          <td key={`${role}-${code}`} className="px-3 py-2 text-center">
                            <label className="inline-flex flex-col items-center gap-1">
                              <input
                                type="checkbox"
                                className="h-4 w-4 rounded border-slate-300 text-brand-600"
                                checked={checked}
                                disabled={overrideMutation.isPending || !cell}
                                onChange={(e) =>
                                  overrideMutation.mutate({
                                    role,
                                    permission_code: code,
                                    allowed: e.target.checked
                                  })
                                }
                              />
                              <span
                                className={`rounded-full px-2 py-0.5 text-[11px] ${
                                  isOverride ? "bg-brand-50 text-brand-700" : "bg-slate-100 text-slate-500"
                                }`}
                              >
                                {isOverride ? "Override" : "Base"}
                              </span>
                            </label>
                          </td>
                        );
                      })}
                    </tr>
                  );
                })}
              </tbody>
            </table>
            {!permissionCodes.length && (
              <p className="mt-3 text-sm text-slate-600">No hay permisos disponibles para este hotel.</p>
            )}
          </div>
        )}

        {matrixQuery.isError && <p className="mt-2 text-sm text-rose-600">No se pudo cargar la matriz.</p>}
        {overrideMutation.isError && (
          <p className="mt-2 text-sm text-rose-600">
            {(overrideMutation.error as Error).message || "No se pudo guardar el permiso"}
          </p>
        )}
      </div>
    </div>
  );
}
