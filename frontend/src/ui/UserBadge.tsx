import { useNavigate } from "react-router-dom";

import { useSession } from "../state/session";

export function UserBadge() {
  const { session, logout, setRole } = useSession();
  const navigate = useNavigate();

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const handleRoleChange = (role: "owner" | "receptionist") => {
    setRole(role);
  };

  const initials = (session.email || session.userId || "??").slice(0, 2).toUpperCase();

  return (
    <div className="flex items-center gap-3 rounded-full border border-slate-200 bg-white px-3 py-1.5 text-sm shadow-sm">
      <div className="grid h-8 w-8 place-items-center rounded-full bg-brand-100 font-semibold text-brand-700">{initials}</div>
      <div className="leading-tight">
        <div className="font-semibold text-slate-900">{session.email || session.userId}</div>
        <div className="text-xs text-slate-500 flex items-center gap-2">
          <span data-testid="session-role">{session.role === "owner" ? "Owner" : "Recepcionista"}</span>
          <span aria-hidden="true">•</span>
          <button
            className="text-brand-700 hover:underline"
            onClick={handleLogout}
            type="button"
            data-testid="logout-btn"
          >
            Logout
          </button>
        </div>
        <div className="mt-1 flex gap-1 text-xs">
          <button
            type="button"
            data-testid="role-owner"
            onClick={() => handleRoleChange("owner")}
            className={`rounded-full px-2 py-1 ${session.role === "owner" ? "bg-brand-100 text-brand-700" : "border border-slate-200 text-slate-600"}`}
          >
            Owner
          </button>
          <button
            type="button"
            data-testid="role-receptionist"
            onClick={() => handleRoleChange("receptionist")}
            className={`rounded-full px-2 py-1 ${session.role === "receptionist" ? "bg-brand-100 text-brand-700" : "border border-slate-200 text-slate-600"}`}
          >
            Recepcionista
          </button>
        </div>
      </div>
    </div>
  );
}
