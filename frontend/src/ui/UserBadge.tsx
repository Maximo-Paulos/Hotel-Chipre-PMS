import { ChangeEvent } from "react";
import { useNavigate } from "react-router-dom";

import { useSession } from "../state/session";
import type { SessionState } from "../state/session";

const roleLabels: Record<SessionState["role"], string> = {
  owner: "Dueño",
  co_owner: "Co-dueño",
  manager: "Manager",
  housekeeping: "Housekeeping"
};

export function UserBadge() {
  const { session, logout, setRole } = useSession();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const handleRoleChange = (event: ChangeEvent<HTMLSelectElement>) => {
    setRole(event.target.value as SessionState["role"]);
  };

  const initials = (session.email || session.userId || "??").slice(0, 2).toUpperCase();

  return (
    <div className="flex items-center gap-3 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm shadow-sm">
      <div className="grid h-8 w-8 place-items-center rounded-full bg-brand-100 font-semibold text-brand-700">{initials}</div>
      <div className="leading-tight">
        <div className="font-semibold text-slate-900">{session.email || session.userId}</div>
        <div className="text-xs text-slate-500 flex items-center gap-2">
          <span data-testid="session-role">{roleLabels[session.role] ?? session.role}</span>
          <span aria-hidden="true">|</span>
          <button
            className="text-brand-700 hover:underline"
            onClick={handleLogout}
            type="button"
            data-testid="logout-btn"
          >
            Logout
          </button>
        </div>
        {(session.baseRole === "owner") && (
          <label className="mt-2 block text-xs text-slate-600">
            <span className="mr-2 font-semibold text-slate-700">Cambiar vista</span>
            <select
              className="rounded border border-slate-200 bg-white px-2 py-1 text-xs text-slate-700 shadow-sm focus:border-brand-400 focus:outline-none"
              value={session.role}
              onChange={handleRoleChange}
              data-testid="role-switcher"
            >
              <option value="owner">Dueño (propietario)</option>
              <option value="co_owner">Co-dueño</option>
              <option value="manager">Manager</option>
              <option value="housekeeping">Housekeeping</option>
            </select>
          </label>
        )}
      </div>
    </div>
  );
}
