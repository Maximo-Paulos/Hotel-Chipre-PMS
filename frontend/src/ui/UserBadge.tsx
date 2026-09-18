import { ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";

import { normalizeRole, useSession } from "../state/session";
import type { SessionState } from "../state/session";

// Exported for AppShell's "Viendo como ..." banner so both places show the
// same label for a given role instead of drifting apart.
export const roleLabels: Record<NonNullable<SessionState["role"]>, string> = {
  owner: "Dueño",
  co_owner: "Copropietario",
  manager: "Gerencia",
  housekeeping: "Limpieza",
  receptionist: "Recepción"
};

const ROLE_PREVIEW_HELP = "Solo cambia la vista; tus permisos efectivos no cambian.";

export function UserBadge() {
  const { session, logout, setRole } = useSession();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const handleRoleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setRole(normalizeRole(event.target.value));
    navigate("/dashboard");
  };

  const identity = session.email || session.userId || "Sin sesión";
  const initials = (session.email || session.userId || "??").slice(0, 2).toUpperCase();
  const currentRole = session.role ?? null;

  // One row, one capsule. The owner's role preview used to stack a select and
  // a help paragraph under the address, which turned the `rounded-full` pill
  // into a tall lozenge and made the header ~180px on every screen. The
  // control stays visible (tests and owners both reach for it directly); the
  // help text moves to the accessible description and the tooltip. Below md
  // the same component sits in the 320px mobile slide-over, where it wraps
  // into a card instead.
  return (
    <div className="flex min-w-0 flex-wrap items-center gap-3 rounded-panel border border-slate-200 bg-white p-2 text-sm shadow-sm md:flex-nowrap md:rounded-full md:py-1 md:pl-1 md:pr-3">
      <div
        aria-hidden="true"
        className="grid h-9 w-9 shrink-0 place-items-center rounded-full bg-brand-100 text-xs font-semibold text-brand-700"
      >
        {initials}
      </div>
      <div className="min-w-0 leading-tight">
        <div data-testid="session-email" className="truncate font-medium text-slate-900" title={identity}>
          {identity}
        </div>
        <div className="flex items-center gap-1.5 text-xs text-slate-500">
          <span data-testid="session-role">{currentRole ? roleLabels[currentRole] : "Sin rol"}</span>
          <span aria-hidden="true">·</span>
          <button
            className="inline-flex min-h-11 items-center font-medium text-brand-700 hover:underline md:min-h-0"
            onClick={handleLogout}
            type="button"
            data-testid="logout-btn"
          >
            Salir
          </button>
        </div>
      </div>
      {session.baseRole === "owner" && (
        <label
          data-testid="role-preview"
          className="flex w-full items-center gap-2 border-t border-slate-200 pt-2 text-xs text-slate-500 md:w-auto md:shrink-0 md:border-l md:border-t-0 md:pl-3 md:pt-0"
          title={ROLE_PREVIEW_HELP}
        >
          <span className="font-medium text-slate-600">Ver como</span>
          <select
            className="h-11 flex-1 rounded-control border border-slate-200 bg-white px-2 text-xs font-medium text-slate-800 focus:border-brand-400 focus:outline-none md:h-9 md:flex-none"
            value={currentRole ?? ""}
            onChange={handleRoleChange}
            data-testid="role-switcher"
            aria-describedby="role-switcher-help"
          >
            <option value="" disabled>
              Seleccionar rol
            </option>
            <option value="owner">Dueño (propietario)</option>
            <option value="co_owner">Copropietario</option>
            <option value="manager">Gerencia</option>
            <option value="housekeeping">Limpieza</option>
            <option value="receptionist">Recepción</option>
          </select>
          <span id="role-switcher-help" className="sr-only">
            {ROLE_PREVIEW_HELP}
          </span>
        </label>
      )}
    </div>
  );
}
