import { useCallback, useEffect, useState } from "react";
import type { FormEvent } from "react";

import { ApiError } from "../../api/client";
import { masterAdminFetch } from "../api";

type ResourceType = "marketing_lead" | "public_inquiry";
type HoldReason = "litigation" | "regulatory" | "contractual" | "other";
type ReleaseReason = "litigation_concluded" | "obligation_ended" | "entered_in_error" | "other";

type Target = {
  resource_type: ResourceType;
  record_id: number;
  masked_email: string;
  retention_anchor_at: string;
};

type Hold = {
  id: number;
  resource_type: ResourceType;
  record_id: number;
  reason_code: HoldReason;
  case_reference: string;
  hold_until: string | null;
  placed_at: string;
  released_at: string | null;
  release_reason_code: ReleaseReason | null;
  release_reference: string | null;
};

const card = "rounded-[2rem] border border-white/10 bg-white/5 p-6 shadow-2xl shadow-black/10 backdrop-blur";
const field = "mt-1 w-full rounded-xl border border-white/10 bg-slate-950/80 px-3 py-3 text-sm text-white outline-none focus:border-amber-300/60";
const primaryButton = "min-h-11 rounded-xl bg-amber-300 px-4 py-2 text-sm font-semibold text-slate-950 transition hover:bg-amber-200 disabled:cursor-not-allowed disabled:opacity-50";
const secondaryButton = "min-h-11 rounded-xl border border-white/15 bg-white/5 px-4 py-2 text-sm font-medium text-slate-100 transition hover:bg-white/10 disabled:cursor-not-allowed disabled:opacity-50";
const legalReferencePattern = "^(CASE|MATTER|LEGAL|REG|CONTRACT|EXP)(-|[.]|_|/)[0-9]{4}(-|[.]|_|/)[0-9]{1,6}((-|[.]|_|/)[0-9]{1,4})?$";
const holdPageSize = 100;

const resourceLabels: Record<ResourceType, string> = {
  marketing_lead: "Interesado (acceso temprano)",
  public_inquiry: "Consulta del formulario público"
};

const reasonLabels: Record<HoldReason, string> = {
  litigation: "Litigio",
  regulatory: "Requerimiento regulatorio",
  contractual: "Obligación contractual",
  other: "Otro motivo documentado"
};

const releaseLabels: Record<ReleaseReason, string> = {
  litigation_concluded: "Litigio concluido",
  obligation_ended: "Obligación finalizada",
  entered_in_error: "Cargado por error",
  other: "Otro motivo documentado"
};

const formatDate = (value: string | null) => {
  if (!value) return "Indefinido";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? value : new Intl.DateTimeFormat("es-AR", { dateStyle: "medium", timeStyle: "short" }).format(date);
};

function errorMessage(error: unknown, fallback: string) {
  return error instanceof ApiError ? error.message : fallback;
}

function holdStatus(hold: Hold) {
  if (hold.released_at) return "Liberado";
  if (hold.hold_until && new Date(hold.hold_until).getTime() <= Date.now()) return "Vencido";
  return "Vigente";
}

export function MasterAdminPrivacyRetentionPage() {
  const [resourceType, setResourceType] = useState<ResourceType>("marketing_lead");
  const [query, setQuery] = useState("");
  const [targets, setTargets] = useState<Target[]>([]);
  const [selected, setSelected] = useState<Target | null>(null);
  const [searching, setSearching] = useState(false);
  const [reason, setReason] = useState<HoldReason>("litigation");
  const [caseReference, setCaseReference] = useState("");
  const [holdUntil, setHoldUntil] = useState("");
  const [releaseReason, setReleaseReason] = useState<ReleaseReason>("litigation_concluded");
  const [releaseReference, setReleaseReference] = useState("");
  const [releasePassword, setReleasePassword] = useState("");
  const [releaseMfaCode, setReleaseMfaCode] = useState("");
  const [releaseHoldId, setReleaseHoldId] = useState<number | null>(null);
  const [holds, setHolds] = useState<Hold[]>([]);
  const [holdsHasMore, setHoldsHasMore] = useState(false);
  const [loadingHolds, setLoadingHolds] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);

  const refreshHolds = useCallback(async () => {
    setLoadingHolds(true);
    try {
      const rows = await masterAdminFetch<Hold[]>(`/api/master-admin/privacy-retention/holds?limit=${holdPageSize}&offset=0`);
      setHolds(rows);
      setHoldsHasMore(rows.length === holdPageSize);
    } catch (loadError) {
      setError(errorMessage(loadError, "No se pudieron cargar las excepciones."));
    } finally {
      setLoadingHolds(false);
    }
  }, []);

  const loadMoreHolds = async () => {
    setLoadingHolds(true);
    setError(null);
    try {
      const limit = Math.min(holds.length + holdPageSize, 500);
      const rows = await masterAdminFetch<Hold[]>(`/api/master-admin/privacy-retention/holds?limit=${limit}&offset=0`);
      setHolds(rows);
      setHoldsHasMore(rows.length === limit && limit < 500);
    } catch (loadError) {
      setError(errorMessage(loadError, "No se pudieron cargar más excepciones."));
    } finally {
      setLoadingHolds(false);
    }
  };

  useEffect(() => {
    void refreshHolds();
  }, [refreshHolds]);

  const searchTargets = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setError(null);
    setNotice(null);
    setSelected(null);
    setSearching(true);
    try {
      const rows = await masterAdminFetch<Target[]>("/api/master-admin/privacy-retention/targets/search", {
        method: "POST",
        data: { resource_type: resourceType, query: query.trim() }
      });
      setTargets(rows);
      if (!rows.length) setNotice("No encontramos coincidencias para ese ID o email exacto.");
    } catch (searchError) {
      setError(errorMessage(searchError, "No se pudo buscar el registro."));
    } finally {
      setSearching(false);
    }
  };

  const createHold = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    if (!selected) return;
    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await masterAdminFetch<Hold>("/api/master-admin/privacy-retention/holds", {
        method: "POST",
        data: {
          resource_type: selected.resource_type,
          record_id: selected.record_id,
          reason_code: reason,
          case_reference: caseReference.trim(),
          hold_until: holdUntil ? new Date(holdUntil).toISOString() : null
        }
      });
      setSelected(null);
      setCaseReference("");
      setHoldUntil("");
      setNotice("La excepción se guardó y quedó registrada en la auditoría.");
      await refreshHolds();
    } catch (createError) {
      setError(errorMessage(createError, "No se pudo crear la excepción."));
    } finally {
      setBusy(false);
    }
  };

  const releaseHold = async (event: FormEvent<HTMLFormElement>, hold: Hold) => {
    event.preventDefault();
    if (!releaseReference.trim()) {
      setError("Ingresá una referencia de liberación antes de continuar.");
      return;
    }
    const confirmed = window.confirm(
      `¿Liberar la excepción del registro ${hold.record_id}? Si ya venció el plazo de 90 días, podrá eliminarse en la próxima purga.`
    );
    if (!confirmed) return;

    setError(null);
    setNotice(null);
    setBusy(true);
    try {
      await masterAdminFetch<Hold>(`/api/master-admin/privacy-retention/holds/${hold.id}/release`, {
        method: "POST",
        data: {
          reason_code: releaseReason,
          case_reference: releaseReference.trim(),
          password: releasePassword,
          mfa_code: releaseMfaCode
        }
      });
      setReleaseHoldId(null);
      setReleaseReference("");
      setReleasePassword("");
      setReleaseMfaCode("");
      setNotice("La excepción se liberó y la decisión quedó auditada.");
      await refreshHolds();
    } catch (releaseError) {
      setError(errorMessage(releaseError, "No se pudo liberar la excepción."));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-6">
      <section className={card}>
        <p className="text-xs uppercase tracking-[0.35em] text-amber-300/80">Privacidad y cumplimiento</p>
        <h2 className="mt-2 text-3xl font-semibold text-white">Retenciones legales</h2>
        <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-300">
          Los leads se eliminan a los 90 días de su última actualización; las consultas, a los 90 días de recibidas.
          Una excepción vigente las excluye temporalmente de la purga. Al vencer o liberarse, no se reinicia el plazo.
        </p>
      </section>

      {error && <p role="alert" className="rounded-2xl border border-rose-400/30 bg-rose-500/10 px-4 py-3 text-sm text-rose-100">{error}</p>}
      {notice && <p role="status" className="rounded-2xl border border-emerald-400/30 bg-emerald-500/10 px-4 py-3 text-sm text-emerald-100">{notice}</p>}

      <section className={card}>
        <h3 className="text-xl font-semibold text-white">Buscar registro</h3>
        <p className="mt-1 text-sm text-slate-300">La búsqueda es por ID o email exacto. El email aparece parcialmente oculto y el término no se guarda en el audit log.</p>
        <form onSubmit={searchTargets} className="mt-5 grid gap-4 md:grid-cols-[minmax(0,1fr)_minmax(0,2fr)_auto] md:items-end">
          <label className="block text-sm text-slate-200">
            Tipo de registro
            <select className={field} value={resourceType} onChange={(event) => { setResourceType(event.target.value as ResourceType); setTargets([]); setSelected(null); }}>
              <option value="marketing_lead">Interesado (acceso temprano)</option>
              <option value="public_inquiry">Consulta del formulario público</option>
            </select>
          </label>
          <label className="block text-sm text-slate-200">
            ID o email exacto
            <input className={field} value={query} onChange={(event) => setQuery(event.target.value)} maxLength={320} required />
          </label>
          <button className={primaryButton} type="submit" disabled={searching || !query.trim()}>{searching ? "Buscando…" : "Buscar"}</button>
        </form>

        {targets.length > 0 && (
          <ul className="mt-5 space-y-2">
            {targets.map((target) => (
              <li key={`${target.resource_type}:${target.record_id}`}>
                <button
                  type="button"
                  onClick={() => setSelected(target)}
                  className={`flex min-h-14 w-full flex-wrap items-center justify-between gap-2 rounded-xl border px-4 py-3 text-left text-sm ${selected?.record_id === target.record_id && selected.resource_type === target.resource_type ? "border-amber-300/70 bg-amber-300/10" : "border-white/10 bg-slate-950/60 hover:bg-white/5"}`}
                >
                  <span className="text-white">ID {target.record_id} · {target.masked_email}</span>
                  <span className="text-xs text-slate-400">El plazo de 90 días corre desde {formatDate(target.retention_anchor_at)}</span>
                </button>
              </li>
            ))}
          </ul>
        )}
      </section>

      {selected && (
        <section className={card}>
          <h3 className="text-xl font-semibold text-white">Crear excepción · ID {selected.record_id}</h3>
          <p className="mt-1 text-sm text-slate-300">{resourceLabels[selected.resource_type]} · {selected.masked_email}</p>
          <form onSubmit={createHold} className="mt-5 grid gap-4 md:grid-cols-2">
            <label className="block text-sm text-slate-200">
              Motivo
              <select className={field} value={reason} onChange={(event) => setReason(event.target.value as HoldReason)}>
                {Object.entries(reasonLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
              </select>
            </label>
            <label className="block text-sm text-slate-200">
              Referencia legal opaca
              <input className={field} value={caseReference} onChange={(event) => setCaseReference(event.target.value.toUpperCase())} placeholder="CASE-2026-41" maxLength={120} pattern={legalReferencePattern} required />
            </label>
            <label className="block text-sm text-slate-200 md:col-span-2">
              Válida hasta (opcional)
              <input className={field} type="datetime-local" value={holdUntil} onChange={(event) => setHoldUntil(event.target.value)} />
              <span className="mt-1 block text-xs text-slate-400">Dejala vacía solo si la obligación requiere retención indefinida, con revisión y liberación explícita.</span>
            </label>
            <p className="md:col-span-2 rounded-xl border border-amber-300/20 bg-amber-300/5 p-3 text-xs leading-5 text-amber-100/90">
              Usá una referencia opaca con formato CASE-AAAA-NÚMERO (por ejemplo, CASE-2026-41); no ingreses nombres, emails, teléfonos ni datos personales. Cada cambio queda en la auditoría Master Admin.
            </p>
            <div className="md:col-span-2"><button className={primaryButton} type="submit" disabled={busy}>{busy ? "Guardando…" : "Crear excepción auditada"}</button></div>
          </form>
        </section>
      )}

      <section className={card}>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h3 className="text-xl font-semibold text-white">Excepciones registradas</h3>
            <p className="mt-1 text-sm text-slate-300">Las excepciones sin liberar aparecen primero; se muestran hasta 500 por consulta. Liberá cada una cuando termine la obligación.</p>
          </div>
          <button type="button" className={secondaryButton} onClick={() => void refreshHolds()} disabled={loadingHolds}>Actualizar</button>
        </div>
        {loadingHolds ? <p className="mt-5 text-sm text-slate-300">Cargando excepciones…</p> : holds.length === 0 ? <p className="mt-5 text-sm text-slate-300">Todavía no hay excepciones registradas.</p> : (
          <ul className="mt-5 space-y-3">
            {holds.map((hold) => (
              <li key={hold.id} className="rounded-2xl border border-white/10 bg-slate-950/50 p-4">
                <div className="flex flex-wrap items-start justify-between gap-3">
                  <div>
                    <p className="font-medium text-white">{resourceLabels[hold.resource_type]} · ID {hold.record_id}</p>
                    <p className="mt-1 text-sm text-slate-300">{reasonLabels[hold.reason_code]} · {hold.case_reference}</p>
                    <p className="mt-1 text-xs text-slate-400">Estado: {holdStatus(hold)} · Hasta: {formatDate(hold.hold_until)} · Creada: {formatDate(hold.placed_at)}</p>
                    {hold.released_at && <p className="mt-1 text-xs text-slate-400">Liberada: {formatDate(hold.released_at)} · {hold.release_reference}</p>}
                  </div>
                </div>
                {!hold.released_at && (
                  releaseHoldId === hold.id ? (
                    <form onSubmit={(event) => void releaseHold(event, hold)} className="mt-4 grid gap-4 rounded-xl border border-amber-300/20 bg-amber-300/5 p-4 md:grid-cols-2">
                      <p className="text-sm leading-6 text-slate-200 md:col-span-2">
                        Para liberar este registro, volvé a autenticarte con tu contraseña y un código MFA nuevo. Si ya pasó el plazo de 90 días, podrá eliminarse en la próxima purga.
                      </p>
                      <label className="block text-sm text-slate-200">
                        Motivo de liberación
                        <select className={field} value={releaseReason} onChange={(event) => setReleaseReason(event.target.value as ReleaseReason)}>
                          {Object.entries(releaseLabels).map(([value, label]) => <option key={value} value={value}>{label}</option>)}
                        </select>
                      </label>
                      <label className="block text-sm text-slate-200">
                        Referencia opaca de cierre
                        <input className={field} value={releaseReference} onChange={(event) => setReleaseReference(event.target.value.toUpperCase())} placeholder="CASE-2026-41" maxLength={120} pattern={legalReferencePattern} required />
                      </label>
                      <label className="block text-sm text-slate-200">
                        Contraseña Master Admin
                        <input className={field} type="password" autoComplete="current-password" value={releasePassword} onChange={(event) => setReleasePassword(event.target.value)} required />
                      </label>
                      <label className="block text-sm text-slate-200">
                        Código MFA actual
                        <input className={field} inputMode="numeric" autoComplete="one-time-code" value={releaseMfaCode} onChange={(event) => setReleaseMfaCode(event.target.value.replace(/\D/g, "").slice(0, 6))} pattern="[0-9]{6}" minLength={6} maxLength={6} required />
                      </label>
                      <div className="flex flex-wrap gap-3 md:col-span-2">
                        <button className={primaryButton} type="submit" disabled={busy || !releaseReference.trim() || !releasePassword || releaseMfaCode.length !== 6}>
                          {busy ? "Verificando…" : "Confirmar liberación"}
                        </button>
                        <button className={secondaryButton} type="button" disabled={busy} onClick={() => { setReleaseHoldId(null); setReleaseReference(""); setReleasePassword(""); setReleaseMfaCode(""); }}>
                          Cancelar
                        </button>
                      </div>
                    </form>
                  ) : (
                    <button
                      type="button"
                      className={`${secondaryButton} mt-4`}
                      disabled={busy}
                      onClick={() => {
                        setReleaseHoldId(hold.id);
                        setReleaseReason("litigation_concluded");
                        setReleaseReference("");
                        setReleasePassword("");
                        setReleaseMfaCode("");
                      }}
                    >
                      Preparar liberación
                    </button>
                  )
                )}
              </li>
            ))}
          </ul>
        )}
        {holdsHasMore && <button type="button" className={`${secondaryButton} mt-4`} onClick={() => void loadMoreHolds()} disabled={loadingHolds}>{loadingHolds ? "Cargando…" : "Cargar siguientes 100"}</button>}
      </section>
    </div>
  );
}
