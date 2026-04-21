import { useEffect } from "react";
import { Link, Navigate, Outlet, useLocation, useNavigate } from "react-router-dom";

import { MasterAdminSessionProvider, useMasterAdminSession } from "./session";

const navItems = [
  { to: "/adminpmsmaster/dashboard", label: "Dashboard" },
  { to: "/adminpmsmaster/billing", label: "Billing Policy" },
  { to: "/adminpmsmaster/email", label: "Email Adapter" },
  { to: "/adminpmsmaster/stripe", label: "Stripe Base" },
  { to: "/adminpmsmaster/audit", label: "Audit Log" }
];

export function MasterAdminRoot() {
  return (
    <MasterAdminSessionProvider>
      <Outlet />
    </MasterAdminSessionProvider>
  );
}

export function MasterAdminIndexRoute() {
  const { status } = useMasterAdminSession();

  if (status === "loading") {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <div className="mx-auto flex min-h-screen max-w-6xl items-center justify-center px-6">
          <div className="rounded-3xl border border-white/10 bg-white/5 px-6 py-4 text-sm text-slate-200">
            Verificando sesión master...
          </div>
        </div>
      </div>
    );
  }

  return <Navigate to={status === "authenticated" ? "/adminpmsmaster/dashboard" : "/adminpmsmaster/login"} replace />;
}

export function MasterAdminProtectedShell() {
  const { status, user, logout } = useMasterAdminSession();
  const navigate = useNavigate();
  const location = useLocation();

  useEffect(() => {
    if (status === "anonymous") {
      navigate("/adminpmsmaster/login", { replace: true, state: { from: location.pathname } });
    }
  }, [location.pathname, navigate, status]);

  if (status === "loading") {
    return (
      <div className="min-h-screen bg-slate-950 text-slate-100">
        <div className="mx-auto flex min-h-screen max-w-6xl items-center justify-center px-6">
          <div className="rounded-3xl border border-white/10 bg-white/5 px-6 py-4 text-sm text-slate-200">
            Cargando panel master...
          </div>
        </div>
      </div>
    );
  }

  if (status === "anonymous") {
    return <Navigate to="/adminpmsmaster/login" replace />;
  }

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(251,191,36,0.14),_transparent_30%),linear-gradient(180deg,#030712_0%,#0f172a_45%,#111827_100%)] text-slate-100">
      <div className="mx-auto flex min-h-screen max-w-7xl gap-6 px-4 py-4 md:px-6">
        <aside className="hidden w-72 shrink-0 rounded-3xl border border-white/10 bg-slate-950/80 p-5 shadow-2xl shadow-black/20 backdrop-blur md:flex md:flex-col">
          <div className="mb-8">
            <p className="text-xs uppercase tracking-[0.3em] text-amber-300/80">Hotel Chipre</p>
            <h1 className="mt-2 text-2xl font-semibold text-white">Owner Master Panel</h1>
            <p className="mt-2 text-sm text-slate-300">Sesión aislada para operaciones de plataforma.</p>
          </div>
          <nav className="space-y-2">
            {navItems.map((item) => (
              <Link
                key={item.to}
                to={item.to}
                className="block rounded-2xl border border-white/5 bg-white/0 px-4 py-3 text-sm text-slate-200 transition hover:border-amber-300/40 hover:bg-white/5 hover:text-white"
              >
                {item.label}
              </Link>
            ))}
          </nav>
          <div className="mt-auto rounded-2xl border border-white/10 bg-white/5 p-4">
            <p className="text-xs uppercase tracking-[0.25em] text-slate-400">Operador</p>
            <p className="mt-2 text-sm font-medium text-white">{user?.email}</p>
            <p className="text-xs text-slate-400">{user?.role}</p>
            <button
              type="button"
              onClick={() => void logout()}
              className="mt-4 rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100 hover:bg-white/10"
            >
              Cerrar sesión
            </button>
          </div>
        </aside>

        <main className="flex-1">
          <div className="mb-4 flex items-center justify-between rounded-3xl border border-white/10 bg-slate-950/70 px-4 py-3 shadow-2xl shadow-black/20 backdrop-blur md:hidden">
            <div>
              <p className="text-xs uppercase tracking-[0.25em] text-amber-300/80">Owner Master Panel</p>
              <p className="text-sm text-slate-300">{user?.email}</p>
            </div>
            <button
              type="button"
              onClick={() => void logout()}
              className="rounded-xl border border-white/10 bg-white/5 px-3 py-2 text-sm text-slate-100"
            >
              Salir
            </button>
          </div>
          <Outlet />
        </main>
      </div>
    </div>
  );
}
