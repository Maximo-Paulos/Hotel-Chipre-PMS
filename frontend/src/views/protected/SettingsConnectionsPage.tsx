import { useState } from "react";
import {
  useConnectIntegration,
  useIntegrations,
  useRefreshIntegration,
  useRevokeIntegration,
} from "../../hooks/useIntegrations";
import { IntegrationHelpDrawer } from "../../components/IntegrationHelpDrawer";
import type { ApiError } from "../../api/client";

type FormState = Record<number, Record<string, string>>;
type NoticeState = Record<number, { tone: "success" | "error" | "info"; message: string }>;

const getErrorMessage = (error: unknown) => {
  if (typeof error === "object" && error !== null && "message" in error) {
    return String((error as ApiError).message);
  }
  return "No se pudo completar la accion.";
};

const connectedSummary: Record<string, string> = {
  mercadopago: "Mercado Pago ya esta conectado a este hotel. Si quieres cambiar de cuenta, primero revoca la conexion.",
  paypal: "PayPal ya esta conectado a este hotel. Puedes refrescar el estado o revocar la conexion.",
  gmail: "Gmail ya esta conectado a este hotel. Puedes revocar la conexion si quieres reemplazar la cuenta.",
  booking: "Booking.com ya esta conectado a este hotel.",
  expedia: "Expedia ya esta conectada a este hotel.",
  whatsapp: "WhatsApp Business ya esta conectado a este hotel.",
};

export function SettingsConnectionsPage() {
  const { data, isLoading, refetch } = useIntegrations();
  const connect = useConnectIntegration();
  const revoke = useRevokeIntegration();
  const refresh = useRefreshIntegration();
  const [form, setForm] = useState<FormState>({});
  const [helpProvider, setHelpProvider] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState>({});

  const setField = (integrationId: number, key: string, value: string) => {
    setForm((prev) => ({
      ...prev,
      [integrationId]: { ...(prev[integrationId] || {}), [key]: value },
    }));
  };

  const setNoticeFor = (integrationId: number, tone: "success" | "error" | "info", message: string) => {
    setNotice((prev) => ({ ...prev, [integrationId]: { tone, message } }));
  };

  const clearCodeField = (integrationId: number) => {
    setForm((prev) => ({
      ...prev,
      [integrationId]: {
        ...(prev[integrationId] || {}),
        code: "",
        access_token: "",
        public_key: "",
        user_id: "",
      },
    }));
  };

  const handleConnect = async (id: number, authType: string) => {
    const payload = form[id] || {};
    try {
      if (authType === "oauth_code" && payload.code?.trim()) {
        await connect.mutateAsync({ id, payload });
        clearCodeField(id);
        setNoticeFor(id, "success", "Conexion guardada de forma segura para este hotel.");
        await refetch();
        return;
      }

      const res = await connect.mutateAsync({ id, payload });
      if (res.redirect_url) {
        window.open(res.redirect_url, "_blank", "width=720,height=880");
        setNoticeFor(
          id,
          "info",
          "Autorizacion iniciada. Cuando el proveedor te entregue el codigo, pegalo aqui y toca Guardar codigo.",
        );
      } else {
        setNoticeFor(id, "success", "Conexion guardada de forma segura para este hotel.");
      }
      await refetch();
    } catch (error) {
      setNoticeFor(id, "error", getErrorMessage(error));
    }
  };

  const handleStartAuthorization = async (id: number) => {
    const payload = form[id] || {};
    if (payload.access_token?.trim()) {
      setNoticeFor(
        id,
        "info",
        "Ya cargaste credenciales manuales. En este caso no uses 'Abrir autorizacion': toca 'Guardar credenciales'.",
      );
      return;
    }
    try {
      const res = await connect.mutateAsync({ id, payload: {} });
      if (res.redirect_url) {
        window.open(res.redirect_url, "_blank", "width=720,height=880");
        setNoticeFor(
          id,
          "info",
          "Autorizacion iniciada. Cuando el proveedor te entregue el codigo, pegalo en el campo 'Codigo de autorizacion' y luego toca 'Guardar codigo'.",
        );
      } else {
        setNoticeFor(id, "error", "El proveedor no devolvio una URL de autorizacion.");
      }
      await refetch();
    } catch (error) {
      setNoticeFor(id, "error", getErrorMessage(error));
    }
  };

  const handleRevoke = async (id: number) => {
    try {
      await revoke.mutateAsync(id);
      setForm((prev) => ({ ...prev, [id]: {} }));
      setNoticeFor(id, "info", "Conexion revocada para este hotel.");
      await refetch();
    } catch (error) {
      setNoticeFor(id, "error", getErrorMessage(error));
    }
  };

  const handleRefresh = async (id: number) => {
    try {
      const result = await refresh.mutateAsync(id);
      setNoticeFor(id, result.status === "error" ? "error" : "success", result.message);
      await refetch();
    } catch (error) {
      setNoticeFor(id, "error", getErrorMessage(error));
    }
  };

  if (isLoading) return <p>Cargando integraciones...</p>;
  if (!data) return <p>Error al cargar integraciones. Verifica la sesion o reintenta.</p>;

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Integraciones</p>
          <h1 className="text-2xl font-semibold text-slate-900">Conexiones</h1>
          <p className="text-sm text-slate-600">Cada conexion se guarda cifrada y vinculada solo al hotel activo.</p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {data.catalog.map((cat) => {
          const conn = data.connections.find((item) => item.integration.id === cat.id);
          const status = conn?.status || "not_connected";
          const currentNotice = notice[cat.id];
          const hasCode = Boolean(form[cat.id]?.code?.trim());
          const hasManualMercadoPagoToken = Boolean(form[cat.id]?.access_token?.trim());
          const isOauth = cat.auth_type === "oauth_code";
          const canSaveOauth = hasCode || hasManualMercadoPagoToken;
          const isConnected = status === "connected";

          return (
            <div key={cat.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold text-slate-900">{cat.display_name}</h2>
                  <p className="text-xs text-slate-500">Auth: {cat.auth_type}</p>
                </div>
                <span className="rounded-full bg-slate-100 px-3 py-1 text-xs font-semibold text-slate-700">
                  {status === "not_connected" ? "No conectado" : status}
                </span>
              </div>

              {cat.doc_url && (
                <a
                  className="text-xs text-brand-700 hover:underline"
                  href={cat.doc_url}
                  target="_blank"
                  rel="noreferrer"
                >
                  Ver documentacion
                </a>
              )}

              {isConnected && (
                <div className="mt-3 rounded-xl border border-emerald-200 bg-emerald-50 px-4 py-3 text-sm text-emerald-800">
                  <p className="font-semibold">Conexion activa</p>
                  <p className="mt-1 text-xs text-emerald-700">
                    {connectedSummary[cat.provider] || "Esta integracion ya esta conectada a este hotel."}
                  </p>
                  {conn?.account_label && (
                    <p className="mt-2 text-xs font-medium text-emerald-800">Cuenta validada: {conn.account_label}</p>
                  )}
                </div>
              )}

              {!isConnected && ["api_key", "signature", "bearer_token"].includes(cat.auth_type) && (
                <div className="mt-3 space-y-2">
                  <p className="text-xs text-slate-600">Ingresa las credenciales requeridas para este hotel.</p>
                  <input
                    className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                    placeholder="api_key / token"
                    value={form[cat.id]?.token || ""}
                    onChange={(e) => setField(cat.id, "token", e.target.value)}
                  />
                  {cat.auth_type === "signature" && (
                    <input
                      className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                      placeholder="api_secret / firma"
                      value={form[cat.id]?.secret || ""}
                      onChange={(e) => setField(cat.id, "secret", e.target.value)}
                    />
                  )}
                  {cat.provider === "whatsapp" && (
                    <>
                      <input
                        className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                        placeholder="phone_number_id"
                        value={form[cat.id]?.phone_number_id || ""}
                        onChange={(e) => setField(cat.id, "phone_number_id", e.target.value)}
                      />
                      <input
                        className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                        placeholder="waba_id"
                        value={form[cat.id]?.waba_id || ""}
                        onChange={(e) => setField(cat.id, "waba_id", e.target.value)}
                      />
                    </>
                  )}
                </div>
              )}

              {!isConnected && isOauth && (
                <div className="mt-3 space-y-3 rounded-xl border border-sky-100 bg-sky-50/70 p-3">
                  <div>
                    <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">Conexion guiada</p>
                    <p className="mt-1 text-xs text-slate-700">
                      1. Toca <strong>Abrir autorizacion</strong>. 2. Copia el codigo que te muestre el proveedor.
                      3. Pegalo abajo en <strong>Codigo de autorizacion</strong>. 4. Toca <strong>Guardar codigo</strong>.
                    </p>
                  </div>

                  <div className="space-y-1">
                    <label className="block text-xs font-semibold text-slate-700">Codigo de autorizacion</label>
                    <input
                      className="w-full rounded border border-slate-200 bg-white px-3 py-2 text-sm"
                      placeholder="Pega aqui el codigo de autorizacion que te devolvio Mercado Pago"
                      value={form[cat.id]?.code || ""}
                      onChange={(e) => setField(cat.id, "code", e.target.value)}
                    />
                    <p className="text-[11px] text-slate-500">
                      Si acabas de autorizar la app, este es el campo donde tienes que pegar el codigo.
                    </p>
                  </div>

                  {cat.provider === "mercadopago" && (
                    <div className="space-y-2 rounded-lg border border-slate-200 bg-white p-3">
                      <p className="text-xs font-semibold text-slate-700">Opcion alternativa: guardar credenciales manuales</p>
                      <p className="text-[11px] text-slate-500">
                        Si OAuth aun no esta habilitado para este PMS, usa este camino. Guarda el access token del hotel sin tocar codigo.
                      </p>
                      <p className="text-xs text-slate-600">
                        Si ya tenes credenciales de Mercado Pago, tambien podes guardarlas directo para este hotel.
                      </p>
                      <input
                        className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                        placeholder="access_token de Mercado Pago"
                        value={form[cat.id]?.access_token || ""}
                        onChange={(e) => setField(cat.id, "access_token", e.target.value)}
                      />
                      <input
                        className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                        placeholder="public_key (opcional)"
                        value={form[cat.id]?.public_key || ""}
                        onChange={(e) => setField(cat.id, "public_key", e.target.value)}
                      />
                      <input
                        className="w-full rounded border border-slate-200 px-3 py-2 text-sm"
                        placeholder="user_id / collector_id (opcional)"
                        value={form[cat.id]?.user_id || ""}
                        onChange={(e) => setField(cat.id, "user_id", e.target.value)}
                      />
                      <p className="text-[11px] font-medium text-emerald-700">
                        Despues de completar estos campos, toca <strong>Guardar credenciales</strong>. No hace falta abrir autorizacion.
                      </p>
                    </div>
                  )}
                </div>
              )}

              {currentNotice && (
                <div
                  className={`mt-3 rounded-lg border px-3 py-2 text-xs ${
                    currentNotice.tone === "success"
                      ? "border-emerald-200 bg-emerald-50 text-emerald-700"
                      : currentNotice.tone === "error"
                        ? "border-rose-200 bg-rose-50 text-rose-700"
                        : "border-sky-200 bg-sky-50 text-sky-700"
                  }`}
                >
                  {currentNotice.message}
                </div>
              )}

              {!isConnected && cat.provider === "mercadopago" && !hasManualMercadoPagoToken && !hasCode && (
                <div className="mt-3 rounded-lg border border-amber-200 bg-amber-50 px-3 py-2 text-xs text-amber-800">
                  Si al tocar <strong>Abrir autorizacion</strong> ves un error del proveedor, usa <strong>access_token</strong> en la opcion alternativa.
                  Ese dato se guarda cifrado y queda asociado solo a este hotel.
                </div>
              )}

              <div className="mt-4 flex flex-wrap gap-2">
                <button
                  className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:border-brand-400"
                  onClick={() => setHelpProvider(cat.provider)}
                  type="button"
                >
                  Como conectar
                </button>
                {!isConnected && isOauth ? (
                  <>
                    {!hasManualMercadoPagoToken && (
                      <button
                        className="rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-sm font-semibold text-sky-700 disabled:opacity-60"
                        onClick={() => handleStartAuthorization(cat.id)}
                        disabled={connect.isPending}
                        type="button"
                      >
                        Abrir autorizacion
                      </button>
                    )}
                    <button
                      className="rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                      onClick={() => handleConnect(cat.id, cat.auth_type)}
                      disabled={connect.isPending || !canSaveOauth}
                      type="button"
                    >
                      {hasManualMercadoPagoToken ? "Guardar credenciales" : "Guardar codigo"}
                    </button>
                  </>
                ) : !isConnected ? (
                  <button
                    className="rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                    onClick={() => handleConnect(cat.id, cat.auth_type)}
                    disabled={connect.isPending}
                    type="button"
                  >
                    {status === "connected" ? "Actualizar conexion" : "Conectar"}
                  </button>
                ) : null}
                {isConnected && (
                  <>
                    <button
                      className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
                      onClick={() => handleRefresh(cat.id)}
                      disabled={refresh.isPending}
                      type="button"
                    >
                      Refrescar
                    </button>
                    <button
                      className="rounded-lg border border-rose-200 px-3 py-2 text-sm font-semibold text-rose-700 disabled:opacity-60"
                      onClick={() => handleRevoke(cat.id)}
                      disabled={revoke.isPending}
                      type="button"
                    >
                      Revocar
                    </button>
                  </>
                )}
              </div>

              {conn?.expires_at && (
                <p className="mt-2 text-xs text-slate-500">Expira: {new Date(conn.expires_at).toLocaleString()}</p>
              )}
              {conn?.last_checked_at && (
                <p className="text-xs text-slate-500">
                  Ultima verificacion: {new Date(conn.last_checked_at).toLocaleString()}
                </p>
              )}
              {conn?.last_error && <p className="mt-2 text-xs text-rose-700">Error: {conn.last_error}</p>}
            </div>
          );
        })}
      </div>

      <IntegrationHelpDrawer provider={helpProvider} open={!!helpProvider} onClose={() => setHelpProvider(null)} />
    </div>
  );
}
