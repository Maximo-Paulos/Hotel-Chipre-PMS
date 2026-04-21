import { useEffect, useState } from "react";

import { ApiError } from "../../api/client";
import { masterAdminFetch } from "../api";

type AuditEvent = {
  id: number;
  actor_user_id: number | null;
  action: string;
  outcome: string;
  target_type: string | null;
  target_id: string | null;
  request_path: string | null;
  request_method: string | null;
  created_at: string;
  metadata_json: string | null;
};

export function MasterAdminAuditPage() {
  const [items, setItems] = useState<AuditEvent[]>([]);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void masterAdminFetch<{ items: AuditEvent[] }>("/api/master-admin/audit/events")
      .then((data) => setItems(data.items))
      .catch((err) => {
        if (err instanceof ApiError) setError(err.message);
        else setError("No se pudo leer el audit log.");
      });
  }, []);

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/10 backdrop-blur">
        <p className="text-xs uppercase tracking-[0.35em] text-amber-300/80">Audit log</p>
        <h2 className="mt-2 text-3xl font-semibold text-white">Trazabilidad</h2>
        <p className="mt-2 text-sm text-slate-300">Cada cambio relevante del panel master deja un registro persistente.</p>
      </section>

      {error && <div className="rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">{error}</div>}

      <section className="rounded-[2rem] border border-white/10 bg-slate-950/50 p-5">
        <div className="overflow-x-auto">
          <table className="min-w-full border-separate border-spacing-y-2 text-sm">
            <thead>
              <tr className="text-left text-xs uppercase tracking-[0.2em] text-slate-400">
                <th className="px-3 py-2">Action</th>
                <th className="px-3 py-2">Outcome</th>
                <th className="px-3 py-2">Target</th>
                <th className="px-3 py-2">At</th>
              </tr>
            </thead>
            <tbody>
              {items.map((event) => (
                <tr key={event.id} className="rounded-2xl bg-white/5">
                  <td className="rounded-l-2xl px-3 py-3 text-white">{event.action}</td>
                  <td className="px-3 py-3 text-slate-200">{event.outcome}</td>
                  <td className="px-3 py-3 text-slate-300">
                    {event.target_type || "system"} {event.target_id ? `· ${event.target_id}` : ""}
                  </td>
                  <td className="rounded-r-2xl px-3 py-3 text-slate-400">{event.created_at}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}

