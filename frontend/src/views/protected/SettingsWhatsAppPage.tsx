import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useMemo, useState } from "react";

import {
  connectWhatsAppIntegration,
  fetchWhatsAppSettings,
  issueWhatsAppApiKey,
  refreshWhatsAppIntegration,
  revokeWhatsAppIntegration
} from "../../api/whatsapp";
import { hasValidSession } from "../../api/client";
import { useSession } from "../../state/session";

const formatDate = (value?: string | null) => (value ? new Date(value).toLocaleString() : "-");

export function SettingsWhatsAppPage() {
  const { session } = useSession();
  const qc = useQueryClient();
  const [credentials, setCredentials] = useState({
    token: "",
    phone_number_id: "",
    waba_id: ""
  });
  const [keyName, setKeyName] = useState("WhatsApp bot");
  const [issuedSecret, setIssuedSecret] = useState<string | null>(null);
  // C4: reads baseRole -- gates fetching real WhatsApp/webhook credentials
  // and issuing bot API keys. Must reflect the real user, not the "Cambiar
  // vista" preview role.
  const canManage = ["owner", "co_owner"].includes(session.baseRole ?? "");

  const settingsQuery = useQuery({
    queryKey: ["whatsapp-settings", session.hotelId],
    enabled: hasValidSession(session) && canManage,
    queryFn: () => fetchWhatsAppSettings(session)
  });
  const connectMutation = useMutation({
    mutationFn: (payload: Record<string, string>) => {
      const whatsapp = settingsQuery.data?.integrationStatus.catalog.find((item) => item.provider === "whatsapp");
      if (!whatsapp) throw new Error("Integracion WhatsApp no encontrada");
      return connectWhatsAppIntegration(whatsapp.id, payload, session);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["whatsapp-settings", session.hotelId] })
  });
  const revokeMutation = useMutation({
    mutationFn: () => {
      const whatsapp = settingsQuery.data?.integrationStatus.catalog.find((item) => item.provider === "whatsapp");
      if (!whatsapp) throw new Error("Integracion WhatsApp no encontrada");
      return revokeWhatsAppIntegration(whatsapp.id, session);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["whatsapp-settings", session.hotelId] })
  });
  const refreshMutation = useMutation({
    mutationFn: () => {
      const whatsapp = settingsQuery.data?.integrationStatus.catalog.find((item) => item.provider === "whatsapp");
      if (!whatsapp) throw new Error("Integracion WhatsApp no encontrada");
      return refreshWhatsAppIntegration(whatsapp.id, session);
    },
    onSuccess: () => qc.invalidateQueries({ queryKey: ["whatsapp-settings", session.hotelId] })
  });
  const issueKeyMutation = useMutation({
    mutationFn: () => issueWhatsAppApiKey({ name: keyName, expires_at: null }, session),
    onSuccess: (res) => {
      setIssuedSecret(res.secret);
      setKeyName("WhatsApp bot");
      qc.invalidateQueries({ queryKey: ["whatsapp-settings", session.hotelId] });
    }
  });

  const activeBotKeys = useMemo(
    () => settingsQuery.data?.apiKeys.filter((key) => key.is_active) || [],
    [settingsQuery.data?.apiKeys]
  );
  const selectedKey = activeBotKeys[0];
  const connection = settingsQuery.data?.connection;
  const status = connection?.status || "not_connected";

  if (!hasValidSession(session)) {
    return <p className="text-sm text-slate-600">Inicia sesion con un hotel activo para configurar WhatsApp.</p>;
  }
  if (!canManage) {
    return <p className="text-sm text-slate-600">Solo owner y co-owner pueden configurar WhatsApp.</p>;
  }

  return (
    <div className="space-y-6">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Settings</p>
        <h1 className="text-2xl font-semibold text-slate-900">WhatsApp</h1>
        <p className="text-sm text-slate-600">
          Configura WhatsApp Business y la API Key usada por el bot publico del hotel.
        </p>
      </header>

      {settingsQuery.isLoading ? (
        <p className="text-sm text-slate-600">Cargando configuracion...</p>
      ) : (
        <>
          <div className="grid gap-4 lg:grid-cols-2">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-sm font-semibold text-slate-800">Conexion WhatsApp Business</h2>
                  <p className="text-xs text-slate-500">Credenciales cifradas por hotel desde Integraciones.</p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                  {status === "not_connected" ? "No conectado" : status}
                </span>
              </div>

              {status !== "connected" ? (
                <div className="mt-3 space-y-2">
                  <input
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    placeholder="Bearer token"
                    value={credentials.token}
                    onChange={(e) => setCredentials((prev) => ({ ...prev, token: e.target.value }))}
                  />
                  <input
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    placeholder="phone_number_id"
                    value={credentials.phone_number_id}
                    onChange={(e) => setCredentials((prev) => ({ ...prev, phone_number_id: e.target.value }))}
                  />
                  <input
                    className="w-full rounded-lg border border-slate-200 px-3 py-2 text-sm"
                    placeholder="waba_id"
                    value={credentials.waba_id}
                    onChange={(e) => setCredentials((prev) => ({ ...prev, waba_id: e.target.value }))}
                  />
                  <button
                    type="button"
                    className="rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                    disabled={connectMutation.isPending || !credentials.token.trim()}
                    onClick={() => connectMutation.mutate(credentials)}
                  >
                    {connectMutation.isPending ? "Guardando..." : "Conectar WhatsApp"}
                  </button>
                </div>
              ) : (
                <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                  <p className="font-semibold">Conexion activa</p>
                  {connection?.account_label && <p className="mt-1 text-xs">Cuenta: {connection.account_label}</p>}
                </div>
              )}

              <div className="mt-4 flex flex-wrap gap-2">
                {status === "connected" && (
                  <>
                    <button
                      type="button"
                      className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
                      disabled={refreshMutation.isPending}
                      onClick={() => refreshMutation.mutate()}
                    >
                      {refreshMutation.isPending ? "Verificando..." : "Refrescar"}
                    </button>
                    <button
                      type="button"
                      className="rounded-lg border border-rose-200 px-3 py-2 text-sm font-semibold text-rose-700 disabled:opacity-60"
                      disabled={revokeMutation.isPending}
                      onClick={() => revokeMutation.mutate()}
                    >
                      Revocar
                    </button>
                  </>
                )}
              </div>

              {connection?.last_checked_at && (
                <p className="mt-2 text-xs text-slate-500">
                  Ultima verificacion: {formatDate(connection.last_checked_at)}
                </p>
              )}
              {connection?.last_error && <p className="mt-2 text-xs text-rose-700">Error: {connection.last_error}</p>}
              {(connectMutation.isError || revokeMutation.isError || refreshMutation.isError) && (
                <p className="mt-2 text-sm text-rose-600">No se pudo actualizar la conexion.</p>
              )}
            </div>

            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <h2 className="text-sm font-semibold text-slate-800">API Key del bot</h2>
              <p className="mt-1 text-xs text-slate-500">
                Los hooks publicos aceptan Authorization: Bearer con una API Key activa de proposito WhatsApp bot.
              </p>

              {selectedKey ? (
                <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                  <p className="font-semibold">Clave activa seleccionada</p>
                  <p className="mt-1 text-xs">
                    {selectedKey.name} - prefijo <code>{selectedKey.key_prefix}</code>
                  </p>
                  <p className="mt-1 text-xs">Creada: {formatDate(selectedKey.created_at)}</p>
                </div>
              ) : (
                <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-900">
                  No hay una API Key activa para WhatsApp. Crea una y copia el secreto en el bot externo.
                </div>
              )}

              <div className="mt-3 flex flex-col gap-2 sm:flex-row">
                <input
                  className="rounded-lg border border-slate-200 px-3 py-2 text-sm"
                  placeholder="Nombre de la clave"
                  value={keyName}
                  onChange={(e) => setKeyName(e.target.value)}
                />
                <button
                  type="button"
                  className="rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white hover:bg-brand-700 disabled:opacity-60"
                  disabled={issueKeyMutation.isPending || !keyName.trim()}
                  onClick={() => issueKeyMutation.mutate()}
                >
                  {issueKeyMutation.isPending ? "Creando..." : "Crear API Key"}
                </button>
              </div>

              {issuedSecret && (
                <div className="mt-3 rounded-xl border border-amber-200 bg-amber-50 p-3">
                  <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Secreto visible una vez</p>
                  <p className="mt-1 text-xs text-amber-900">Copialo ahora. No se volvera a mostrar.</p>
                  <div className="mt-2 flex flex-col gap-2 sm:flex-row sm:items-center">
                    <code className="break-all rounded-lg border border-amber-200 bg-white px-3 py-2 text-xs">
                      {issuedSecret}
                    </code>
                    <button
                      type="button"
                      className="rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white"
                      onClick={() => navigator.clipboard?.writeText(issuedSecret)}
                    >
                      Copiar
                    </button>
                  </div>
                </div>
              )}
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-800">Hooks del bot</h2>
            <p className="mt-1 text-xs text-slate-500">Base: {settingsQuery.data?.hookBaseUrl}</p>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold text-slate-600">Uso</th>
                    <th className="px-3 py-2 text-left font-semibold text-slate-600">Metodo</th>
                    <th className="px-3 py-2 text-left font-semibold text-slate-600">URL</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {(settingsQuery.data?.endpoints || []).map((endpoint) => (
                    <tr key={`${endpoint.method}-${endpoint.url}`}>
                      <td className="px-3 py-2">{endpoint.label}</td>
                      <td className="px-3 py-2">
                        <span className="rounded bg-slate-100 px-2 py-1 text-xs font-semibold text-slate-700">
                          {endpoint.method}
                        </span>
                      </td>
                      <td className="px-3 py-2">
                        <code className="break-all text-xs text-slate-700">{endpoint.url}</code>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
            <h2 className="text-sm font-semibold text-slate-800">API Keys WhatsApp existentes</h2>
            <div className="mt-3 overflow-x-auto">
              <table className="min-w-full divide-y divide-slate-200 text-sm">
                <thead className="bg-slate-50">
                  <tr>
                    <th className="px-3 py-2 text-left font-semibold text-slate-600">Nombre</th>
                    <th className="px-3 py-2 text-left font-semibold text-slate-600">Prefijo</th>
                    <th className="px-3 py-2 text-left font-semibold text-slate-600">Estado</th>
                    <th className="px-3 py-2 text-left font-semibold text-slate-600">Ultimo uso</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200">
                  {(settingsQuery.data?.apiKeys || []).map((key) => (
                    <tr key={key.id}>
                      <td className="px-3 py-2">{key.name}</td>
                      <td className="px-3 py-2">
                        <code className="rounded bg-slate-100 px-2 py-1 text-xs">{key.key_prefix}</code>
                      </td>
                      <td className="px-3 py-2">
                        {key.is_active ? (
                          <span className="rounded-full bg-emerald-50 px-2 py-1 text-xs text-emerald-700">
                            Activa
                          </span>
                        ) : (
                          <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
                            Revocada
                          </span>
                        )}
                      </td>
                      <td className="px-3 py-2">{formatDate(key.last_used_at)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}

      {settingsQuery.isError && <p className="text-sm text-rose-600">No se pudo cargar WhatsApp.</p>}
      {issueKeyMutation.isError && <p className="text-sm text-rose-600">No se pudo crear la API Key.</p>}
    </div>
  );
}
