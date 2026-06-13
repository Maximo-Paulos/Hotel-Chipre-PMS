import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";

import {
  issueApiKey,
  listApiKeys,
  revokeApiKey,
  type ApiKeyPurpose,
  type HotelApiKeyIssued,
  type IssueHotelApiKeyPayload
} from "../../api/apiKeys";
import { hasValidSession } from "../../api/client";
import { useSession } from "../../state/session";

const purposeLabels: Record<ApiKeyPurpose, string> = {
  whatsapp_bot: "WhatsApp bot",
  web_engine: "Motor web",
  channel_manager: "Channel manager",
  reporting: "Reporting",
  other: "Otro"
};

const purposeOptions: ApiKeyPurpose[] = ["whatsapp_bot", "web_engine", "channel_manager", "reporting", "other"];

const emptyForm: IssueHotelApiKeyPayload = {
  name: "",
  purpose: "whatsapp_bot",
  expires_at: null
};

const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleString() : "-");

export function SettingsApiKeysPage() {
  const { session } = useSession();
  const qc = useQueryClient();
  const [form, setForm] = useState<IssueHotelApiKeyPayload>(emptyForm);
  const [issuedKey, setIssuedKey] = useState<HotelApiKeyIssued | null>(null);

  const canManage = ["owner", "co_owner"].includes(session.role ?? "");
  const keysQuery = useQuery({
    queryKey: ["api-keys", session.hotelId],
    enabled: hasValidSession(session) && canManage,
    queryFn: () => listApiKeys(session)
  });
  const issueMutation = useMutation({
    mutationFn: (payload: IssueHotelApiKeyPayload) => issueApiKey(payload, session),
    onSuccess: (res) => {
      setIssuedKey(res);
      setForm(emptyForm);
      qc.invalidateQueries({ queryKey: ["api-keys", session.hotelId] });
    }
  });
  const revokeMutation = useMutation({
    mutationFn: (keyId: number) => revokeApiKey(keyId, session),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["api-keys", session.hotelId] })
  });

  if (!hasValidSession(session)) {
    return <p className="text-sm text-slate-600">Inicia sesion con un hotel activo para administrar API Keys.</p>;
  }
  if (!canManage) {
    return <p className="text-sm text-slate-600">Solo owner y co-owner pueden administrar API Keys.</p>;
  }

  const activeKeys = keysQuery.data?.filter((key) => key.is_active) || [];

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Settings</p>
        <h1 className="text-2xl font-semibold text-slate-900">API Keys</h1>
        <p className="text-sm text-slate-600">Crea, identifica por prefijo y revoca claves publicas del hotel.</p>
      </header>

      {issuedKey && (
        <div className="rounded-xl border border-amber-200 bg-amber-50 p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Clave creada</p>
          <h2 className="mt-1 text-sm font-semibold text-amber-950">Copia este secreto ahora</h2>
          <p className="mt-1 text-xs text-amber-900">
            Este valor se muestra una sola vez. El PMS solo guardara el hash y no podra volver a mostrarlo.
          </p>
          <div className="mt-3 flex flex-col gap-2 sm:flex-row sm:items-center">
            <code className="break-all rounded-lg border border-amber-200 bg-white px-3 py-2 text-xs text-slate-800">
              {issuedKey.secret}
            </code>
            <button
              type="button"
              className="rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700"
              onClick={() => navigator.clipboard?.writeText(issuedKey.secret)}
            >
              Copiar
            </button>
            <button
              type="button"
              className="rounded-lg border border-amber-300 px-3 py-2 text-sm font-semibold text-amber-900"
              onClick={() => setIssuedKey(null)}
            >
              Ocultar
            </button>
          </div>
        </div>
      )}

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <h2 className="text-sm font-semibold text-slate-800">Emitir nueva API Key</h2>
        <div className="mt-3 grid gap-3 md:grid-cols-4">
          <input
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            placeholder="Nombre visible"
            value={form.name}
            onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
          />
          <select
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            value={form.purpose}
            onChange={(e) => setForm((prev) => ({ ...prev, purpose: e.target.value as ApiKeyPurpose }))}
          >
            {purposeOptions.map((purpose) => (
              <option key={purpose} value={purpose}>
                {purposeLabels[purpose]}
              </option>
            ))}
          </select>
          <input
            className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
            type="datetime-local"
            value={form.expires_at ? form.expires_at.slice(0, 16) : ""}
            onChange={(e) =>
              setForm((prev) => ({
                ...prev,
                expires_at: e.target.value ? new Date(e.target.value).toISOString() : null
              }))
            }
          />
          <button
            type="button"
            onClick={() => issueMutation.mutate(form)}
            disabled={issueMutation.isPending || !form.name.trim()}
            className="rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-brand-700 disabled:opacity-60"
          >
            {issueMutation.isPending ? "Creando..." : "Crear clave"}
          </button>
        </div>
        {issueMutation.isError && (
          <p className="mt-2 text-sm text-rose-600">
            {(issueMutation.error as Error).message || "No se pudo crear la clave"}
          </p>
        )}
      </div>

      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <div className="flex items-center justify-between">
          <h2 className="text-sm font-semibold text-slate-800">Claves del hotel</h2>
          <span className="text-xs text-slate-500">
            {keysQuery.isFetching ? "Actualizando..." : `${activeKeys.length} activas`}
          </span>
        </div>
        <div className="mt-3 overflow-x-auto">
          <table className="min-w-full divide-y divide-slate-200 text-sm">
            <thead className="bg-slate-50">
              <tr>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">Nombre</th>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">Prefijo</th>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">Uso</th>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">Estado</th>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">Ultimo uso</th>
                <th className="px-3 py-2 text-left font-semibold text-slate-600">Expira</th>
                <th className="px-3 py-2 text-right font-semibold text-slate-600">Acciones</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-slate-200">
              {(keysQuery.data || []).map((key) => (
                <tr key={key.id}>
                  <td className="px-3 py-2">{key.name}</td>
                  <td className="px-3 py-2">
                    <code className="rounded bg-slate-100 px-2 py-1 text-xs">{key.key_prefix}</code>
                  </td>
                  <td className="px-3 py-2">{purposeLabels[key.purpose] || key.purpose}</td>
                  <td className="px-3 py-2">
                    {key.is_active ? (
                      <span className="rounded-full bg-emerald-50 px-2 py-1 text-xs text-emerald-700">Activa</span>
                    ) : (
                      <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">Revocada</span>
                    )}
                  </td>
                  <td className="px-3 py-2">{formatDate(key.last_used_at)}</td>
                  <td className="px-3 py-2">{formatDate(key.expires_at)}</td>
                  <td className="px-3 py-2 text-right">
                    {key.is_active && (
                      <button
                        type="button"
                        onClick={() => revokeMutation.mutate(key.id)}
                        disabled={revokeMutation.isPending}
                        className="text-sm font-semibold text-rose-600 hover:underline disabled:opacity-60"
                      >
                        Revocar
                      </button>
                    )}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
          {keysQuery.isError && <p className="mt-2 text-sm text-rose-600">No se pudieron cargar las claves.</p>}
          {revokeMutation.isError && (
            <p className="mt-2 text-sm text-rose-600">
              {(revokeMutation.error as Error).message || "No se pudo revocar la clave"}
            </p>
          )}
        </div>
      </div>
    </div>
  );
}
