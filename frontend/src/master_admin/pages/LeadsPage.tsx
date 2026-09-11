import { useEffect, useMemo, useState } from "react";

import { toCsvCell } from "../../utils/csvCell";
import { masterAdminFetch } from "../api";

/**
 * Everyone who asked for access from hotels-pms.com.
 *
 * Read-only on purpose. The export is built in the browser from the rows
 * already loaded, so it needs no second endpoint -- and because every cell
 * was typed by an anonymous visitor, it goes through toCsvCell before the
 * owner opens it in a spreadsheet.
 *
 * Styled with the console's own dark tokens (see BillingPage and the
 * dashboard hotel table), not the tenant app's light ones.
 */
type Lead = {
  id: number;
  email: string;
  name: string | null;
  hotel_name: string | null;
  rooms_estimate: number | null;
  city: string | null;
  phone: string | null;
  source: string;
  created_at: string;
};

const SOURCE_LABELS: Record<string, string> = {
  hero: "Inicio de la página",
  final: "Cierre de la página",
  landing: "Landing"
};

const DATE = new Intl.DateTimeFormat("es-AR", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit"
});

const formatDate = (iso: string) => {
  const parsed = new Date(iso);
  return Number.isNaN(parsed.getTime()) ? iso : DATE.format(parsed);
};

const sourceLabel = (source: string) => SOURCE_LABELS[source] ?? source;

const HEADERS = ["Fecha", "Email", "Nombre", "Hotel", "Habitaciones", "Ciudad", "Teléfono", "Origen"];

const toCsv = (leads: Lead[]) =>
  [
    HEADERS.join(","),
    ...leads.map((lead) =>
      [
        formatDate(lead.created_at),
        lead.email,
        lead.name,
        lead.hotel_name,
        lead.rooms_estimate,
        lead.city,
        lead.phone,
        sourceLabel(lead.source)
      ]
        .map(toCsvCell)
        .join(",")
    )
  ].join("\r\n");

const secondaryButton =
  "rounded-2xl border border-white/15 bg-white/5 px-5 py-3 text-sm font-semibold text-slate-100 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";

function Contact({ lead }: { lead: Lead }) {
  return (
    <>
      <a href={`mailto:${lead.email}`} className="font-medium text-amber-200 [overflow-wrap:anywhere] hover:underline sm:whitespace-nowrap">
        {lead.email}
      </a>
      {lead.name ? <div className="text-slate-200">{lead.name}</div> : null}
      {lead.phone ? <div className="text-xs tabular-nums text-slate-400">{lead.phone}</div> : null}
    </>
  );
}

export function MasterAdminLeadsPage() {
  const [leads, setLeads] = useState<Lead[]>([]);
  const [total, setTotal] = useState(0);
  const [status, setStatus] = useState<"loading" | "ready" | "error">("loading");
  const [query, setQuery] = useState("");

  useEffect(() => {
    let cancelled = false;
    masterAdminFetch<{ items: Lead[]; total: number }>("/api/master-admin/leads?limit=1000")
      .then((data) => {
        if (cancelled) return;
        setLeads(data.items);
        setTotal(data.total);
        setStatus("ready");
      })
      .catch(() => {
        if (!cancelled) setStatus("error");
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return leads;
    return leads.filter((lead) =>
      [lead.email, lead.name, lead.hotel_name, lead.city, lead.phone]
        .filter(Boolean)
        .some((value) => String(value).toLowerCase().includes(needle))
    );
  }, [leads, query]);

  const download = () => {
    // BOM so Excel reads the accents as UTF-8 instead of mojibake.
    const blob = new Blob(["﻿", toCsv(filtered)], { type: "text/csv;charset=utf-8" });
    const url = URL.createObjectURL(blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `hotels-pms-interesados-${new Date().toISOString().slice(0, 10)}.csv`;
    link.click();
    URL.revokeObjectURL(url);
  };

  return (
    <div className="space-y-6">
      <section className="rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/10 backdrop-blur">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-xs uppercase tracking-[0.35em] text-amber-300/80">Sitio público</p>
            <h2 className="mt-2 text-3xl font-semibold text-white">Interesados</h2>
            <p className="mt-2 max-w-3xl text-sm text-slate-300">
              Quienes pidieron acceso desde hotels-pms.com, del más nuevo al más viejo. Si alguien se
              anota dos veces con el mismo mail, aparece una sola vez con los datos más completos.
            </p>
          </div>
          <button type="button" onClick={download} disabled={!filtered.length} className={`${secondaryButton} shrink-0 self-start whitespace-nowrap sm:self-auto`}>
            Descargar CSV
          </button>
        </div>
      </section>

      {status === "error" ? (
        <p role="alert" className="rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">
          No se pudieron cargar los interesados. Volvé a entrar a la consola y probá de nuevo.
        </p>
      ) : null}

      {status === "loading" ? (
        <p className="rounded-3xl border border-white/10 bg-white/5 px-6 py-4 text-sm text-slate-200">Cargando…</p>
      ) : null}

      {status === "ready" && !leads.length ? (
        <p className="rounded-[2rem] border border-dashed border-white/15 bg-white/5 p-8 text-sm text-slate-300">
          Todavía nadie pidió acceso. Cuando alguien complete el formulario de hotels-pms.com aparece acá.
        </p>
      ) : null}

      {status === "ready" && leads.length ? (
        <>
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <p className="text-sm text-slate-300">
              <span className="font-semibold tabular-nums text-white">{total}</span>{" "}
              {total === 1 ? "interesado" : "interesados"}
              {query ? (
                <>
                  {" "}
                  · <span className="tabular-nums text-white">{filtered.length}</span> coinciden
                </>
              ) : null}
            </p>
            <label className="w-full sm:w-80">
              <span className="sr-only">Buscar interesados</span>
              <input
                type="search"
                value={query}
                onChange={(event) => setQuery(event.target.value)}
                placeholder="Buscar por mail, hotel o ciudad"
                className="w-full rounded-2xl border border-white/10 bg-white/5 px-4 py-3 text-sm text-white outline-none placeholder:text-slate-500 focus:border-amber-300/60"
              />
            </label>
          </div>

          {query && !filtered.length ? (
            <p className="rounded-3xl border border-white/10 bg-white/5 px-6 py-4 text-sm text-slate-200">
              Nadie coincide con «{query}».
            </p>
          ) : null}

          {/* Phone: one card per lead, so nothing hides behind a sideways scroll. */}
          <ul className="space-y-2 sm:hidden">
            {filtered.map((lead) => (
              <li key={lead.id} className="rounded-2xl bg-white/5 p-4 text-sm text-slate-100">
                <Contact lead={lead} />
                <dl className="mt-3 grid grid-cols-2 gap-x-3 gap-y-1 text-xs">
                  <dt className="text-slate-400">Hotel</dt>
                  <dd className="min-w-0 text-right [overflow-wrap:anywhere] text-slate-100">{lead.hotel_name ?? "—"}</dd>
                  <dt className="text-slate-400">Habitaciones</dt>
                  <dd className="min-w-0 text-right [overflow-wrap:anywhere] tabular-nums text-slate-100">{lead.rooms_estimate ?? "—"}</dd>
                  <dt className="text-slate-400">Ciudad</dt>
                  <dd className="min-w-0 text-right [overflow-wrap:anywhere] text-slate-100">{lead.city ?? "—"}</dd>
                  <dt className="text-slate-400">Fecha</dt>
                  <dd className="min-w-0 text-right [overflow-wrap:anywhere] tabular-nums text-slate-100">{formatDate(lead.created_at)}</dd>
                </dl>
              </li>
            ))}
          </ul>

          <div className="hidden overflow-x-auto sm:block">
            <table className="min-w-full border-separate border-spacing-y-2 text-sm">
              <thead>
                <tr className="text-left text-xs uppercase tracking-[0.2em] text-slate-400">
                  <th scope="col" className="px-3 py-2">Fecha</th>
                  <th scope="col" className="px-3 py-2">Contacto</th>
                  <th scope="col" className="px-3 py-2">Hotel</th>
                  <th scope="col" className="px-3 py-2 text-right">Hab.</th>
                  <th scope="col" className="px-3 py-2">Ciudad</th>
                  <th scope="col" className="px-3 py-2">Origen</th>
                </tr>
              </thead>
              <tbody>
                {filtered.map((lead) => (
                  <tr key={lead.id} className="bg-white/5 align-top text-slate-100">
                    <td className="whitespace-nowrap rounded-l-2xl px-3 py-3 tabular-nums text-slate-300">
                      {formatDate(lead.created_at)}
                    </td>
                    <td className="px-3 py-3">
                      <Contact lead={lead} />
                    </td>
                    <td className="px-3 py-3">{lead.hotel_name ?? "—"}</td>
                    <td className="px-3 py-3 text-right tabular-nums">{lead.rooms_estimate ?? "—"}</td>
                    <td className="px-3 py-3">{lead.city ?? "—"}</td>
                    <td className="whitespace-nowrap rounded-r-2xl px-3 py-3 text-slate-400">
                      {sourceLabel(lead.source)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      ) : null}
    </div>
  );
}

export default MasterAdminLeadsPage;
