import { useEffect, useState } from "react";

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
type ManualCodeState = Record<number, boolean>;

const getErrorMessage = (error: unknown) => {
  if (typeof error === "object" && error !== null && "message" in error) {
    return String((error as ApiError).message);
  }
  return "No se pudo completar la accion.";
};

const getProviderErrorMessage = (provider: string, error: unknown) => {
  const message = getErrorMessage(error);
  if (provider === "gmail" && message.includes("OAuth de Gmail no esta configurado")) {
    return "Todavia falta configurar la app OAuth de Google del lado de PMS Paulus para este entorno de testing. Cuando carguemos GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET y GMAIL_REDIRECT_URI, este boton abrira Google directamente para el hotel.";
  }
  return message;
};

const connectedSummary: Record<string, string> = {
  mercadopago: "Mercado Pago ya esta conectado a este hotel. Si quieres cambiar de cuenta, primero revoca la conexion.",
  paypal: "PayPal ya esta conectado a este hotel. Puedes refrescar el estado o revocar la conexion.",
  gmail: "Gmail ya esta conectado a este hotel. Este email sera el remitente del hotel para links de pago, recibos y mensajes a huespedes.",
  booking: "Booking.com ya esta conectado a este hotel.",
  expedia: "Expedia ya esta conectada a este hotel.",
  whatsapp: "WhatsApp Business ya esta conectado a este hotel.",
};

const providerPriority: Record<string, number> = {
  gmail: 0,
  mercadopago: 1,
  paypal: 2,
  booking: 3,
  expedia: 4,
  whatsapp: 5,
};

export function SettingsConnectionsPage() {
  const { data, isLoading, refetch } = useIntegrations();
  const connect = useConnectIntegration();
  const revoke = useRevokeIntegration();
  const refresh = useRefreshIntegration();
  const [form, setForm] = useState<FormState>({});
  const [helpProvider, setHelpProvider] = useState<string | null>(null);
  const [notice, setNotice] = useState<NoticeState>({});
  const [showManualCode, setShowManualCode] = useState<ManualCodeState>({});
  const [inlineGuideProvider, setInlineGuideProvider] = useState<string | null>(null);

  useEffect(() => {
    const handleMessage = async (event: MessageEvent) => {
      const payload = event.data as
        | {
            type?: string;
            integrationId?: number;
            status?: "connected" | "error" | string;
            message?: string;
          }
        | undefined;
      if (!payload || payload.type !== "integration-oauth-result" || typeof payload.integrationId !== "number") {
        return;
      }
      setNoticeFor(
        payload.integrationId,
        payload.status === "connected" ? "success" : "error",
        payload.message || (payload.status === "connected" ? "Conexion completada." : "No se pudo completar la conexion."),
      );
      await refetch();
    };

    window.addEventListener("message", handleMessage);
    return () => window.removeEventListener("message", handleMessage);
  }, [refetch]);

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

  const toggleManualCode = (integrationId: number) => {
    setShowManualCode((prev) => ({
      ...prev,
      [integrationId]: !prev[integrationId],
    }));
  };

  const toggleInlineGuide = (provider: string) => {
    setInlineGuideProvider((prev) => (prev === provider ? null : provider));
  };

  const handleConnect = async (id: number, authType: string) => {
    const payload = form[id] || {};
    const catalogItem = data?.catalog.find((item) => item.id === id);
    const provider = catalogItem?.provider || "";
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
          "Autorizacion iniciada. Si el proveedor no vuelve solo al PMS, puedes usar el ingreso manual con codigo como respaldo.",
        );
      } else {
        setNoticeFor(id, "success", "Conexion guardada de forma segura para este hotel.");
      }
      await refetch();
    } catch (error) {
      setNoticeFor(id, "error", getProviderErrorMessage(provider, error));
    }
  };

  const handleStartAuthorization = async (id: number, provider: string) => {
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
          provider === "gmail"
            ? "Autorizacion iniciada. Cuando termines en Google, la conexion deberia completarse sola en esta pantalla. Si Google no redirige bien, usa el campo de codigo como respaldo."
            : "Autorizacion iniciada. Cuando el proveedor te entregue el codigo, pegalo en el campo 'Codigo de autorizacion' y luego toca 'Guardar codigo'.",
        );
      } else {
        setNoticeFor(id, "error", "El proveedor no devolvio una URL de autorizacion.");
      }
      await refetch();
    } catch (error) {
      setNoticeFor(id, "error", getProviderErrorMessage(provider, error));
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

  const orderedCatalog = [...data.catalog].sort((a, b) => {
    const left = providerPriority[a.provider] ?? 99;
    const right = providerPriority[b.provider] ?? 99;
    if (left !== right) return left - right;
    return a.display_name.localeCompare(b.display_name);
  });

  return (
    <div className="space-y-4">
      <div className="flex items-center justify-between">
        <div>
          <p className="text-xs uppercase tracking-wide text-slate-500">Integraciones</p>
          <h1 className="text-2xl font-semibold text-slate-900">Conexiones</h1>
          <p className="text-sm text-slate-600">Cada conexion se guarda cifrada y vinculada solo al hotel activo.</p>
        </div>
      </div>

      <div className="rounded-2xl border border-amber-200 bg-amber-50 p-4 shadow-sm">
          <p className="text-xs font-semibold uppercase tracking-wide text-amber-700">Paso recomendado</p>
          <h2 className="mt-1 text-lg font-semibold text-amber-950">Primero conecta Gmail</h2>
          <p className="mt-2 text-sm text-amber-900">
            Antes de probar cobros o mensajes, conecta el email operativo del hotel. Si Gmail no esta conectado, el sistema no envia links de pago a nombre del hotel.
          </p>
      </div>

      <div className="grid gap-4 md:grid-cols-2">
        {orderedCatalog.map((cat) => {
          const conn = data.connections.find((item) => item.integration.id === cat.id);
          const status = conn?.status || "not_connected";
          const currentNotice = notice[cat.id];
          const hasCode = Boolean(form[cat.id]?.code?.trim());
          const hasManualMercadoPagoToken = Boolean(form[cat.id]?.access_token?.trim());
          const isOauth = cat.auth_type === "oauth_code";
          const canSaveOauth = hasCode || hasManualMercadoPagoToken;
          const isConnected = status === "connected";
          const isGmail = cat.provider === "gmail";
          const manualCodeVisible = Boolean(showManualCode[cat.id]);

          return (
            <div key={cat.id} className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
              <div className="flex items-center justify-between">
                <div>
                  <div className="flex items-center gap-2">
                    <h2 className="text-lg font-semibold text-slate-900">{cat.display_name}</h2>
                    {cat.provider === "gmail" && (
                      <span className="rounded-full bg-amber-100 px-2 py-0.5 text-[11px] font-semibold text-amber-800">
                        Recomendado primero
                      </span>
                    )}
                  </div>
                  <p className="text-xs text-slate-500">{isGmail ? "Correo del hotel" : `Auth: ${cat.auth_type}`}</p>
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
                  {isGmail ? (
                    <div className="flex items-center justify-between rounded-lg border border-sky-200 bg-white px-3 py-2">
                      <div>
                        <p className="text-xs font-semibold text-slate-900">Conexion simple por Google</p>
                        <p className="text-[11px] text-slate-600">
                          La opcion principal abre Google y vuelve sola al PMS.
                        </p>
                      </div>
                      <button
                        className="flex h-7 w-7 items-center justify-center rounded-full border border-sky-200 text-sm font-bold text-sky-700 hover:bg-sky-50"
                        onClick={() => toggleInlineGuide(cat.provider)}
                        type="button"
                        title="Como conectar Gmail"
                        aria-label="Como conectar Gmail"
                      >
                        i
                      </button>
                    </div>
                  ) : (
                    <div>
                      <p className="text-xs font-semibold uppercase tracking-wide text-sky-700">Conexion guiada</p>
                      <p className="mt-1 text-xs text-slate-700">
                        1. Toca Abrir autorizacion. 2. Copia el codigo que te muestre el proveedor. 3. Pegalo abajo en Codigo de autorizacion. 4. Toca Guardar codigo.
                      </p>
                    </div>
                  )}

                  {(!isGmail || manualCodeVisible) && (
                    <div className="space-y-1">
                      <label className="block text-xs font-semibold text-slate-700">Codigo de autorizacion</label>
                      <input
                        className="w-full rounded border border-slate-200 bg-white px-3 py-2 text-sm"
                        placeholder={
                          isGmail
                            ? "Pega aqui el codigo de Google solo si la ventana no vuelve sola al PMS"
                            : "Pega aqui el codigo de autorizacion que te devolvio el proveedor"
                        }
                        value={form[cat.id]?.code || ""}
                        onChange={(e) => setField(cat.id, "code", e.target.value)}
                      />
                      <p className="text-[11px] text-slate-500">
                        {isGmail
                          ? "Este campo es solo un respaldo por si Google no completa la vuelta automatica."
                          : "Si acabas de autorizar la app, este es el campo donde tienes que pegar el codigo."}
                      </p>
                    </div>
                  )}

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

              {!isConnected && cat.provider === "gmail" && (
                <div className="mt-3 rounded-lg border border-sky-200 bg-sky-50 px-3 py-2 text-xs text-sky-800">
                  Este Gmail se usara para enviar mensajes del hotel a sus huespedes. La conexion principal se hace desde la ventana de Google; el codigo manual queda solo como respaldo.
                </div>
              )}

              <div className="mt-4 flex flex-wrap gap-2">
                {!isConnected && isOauth ? (
                  <>
                    {!hasManualMercadoPagoToken && (
                      <button
                        className="rounded-lg bg-brand-600 px-4 py-2.5 text-sm font-semibold text-white disabled:opacity-60"
                        onClick={() => handleStartAuthorization(cat.id, cat.provider)}
                        disabled={connect.isPending}
                        type="button"
                      >
                        {isGmail ? "Conectar Gmail" : "Abrir autorizacion"}
                      </button>
                    )}
                    {isGmail ? (
                      <>
                        <button
                          className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:border-brand-300"
                          onClick={() => toggleInlineGuide(cat.provider)}
                          type="button"
                        >
                          Como conectar
                        </button>
                        {!manualCodeVisible ? (
                          <button
                            className="rounded-lg px-2 py-2 text-xs font-medium text-slate-500 hover:text-slate-700"
                            onClick={() => toggleManualCode(cat.id)}
                            type="button"
                          >
                            Tengo un codigo manual
                          </button>
                        ) : (
                          <>
                            <button
                              className="rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-60"
                              onClick={() => handleConnect(cat.id, cat.auth_type)}
                              disabled={connect.isPending || !canSaveOauth}
                              type="button"
                            >
                              Conectar con codigo
                            </button>
                            <button
                              className="rounded-lg px-2 py-2 text-xs font-medium text-slate-500 hover:text-slate-700"
                              onClick={() => toggleManualCode(cat.id)}
                              type="button"
                            >
                              Ocultar codigo manual
                            </button>
                          </>
                        )}
                      </>
                    ) : (
                      <>
                        <button
                          className="rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:border-brand-400"
                          onClick={() => setHelpProvider(cat.provider)}
                          type="button"
                        >
                          Como conectar
                        </button>
                        <button
                          className="rounded-lg bg-brand-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-60"
                          onClick={() => handleConnect(cat.id, cat.auth_type)}
                          disabled={connect.isPending || !canSaveOauth}
                          type="button"
                        >
                          {hasManualMercadoPagoToken ? "Guardar credenciales" : "Guardar codigo"}
                        </button>
                      </>
                    )}
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

              {isGmail && !isConnected && inlineGuideProvider === cat.provider && (
                <div className="mt-3 rounded-xl border border-sky-200 bg-sky-50 p-3 text-xs text-sky-900">
                  <p className="font-semibold">Como conectar Gmail</p>
                  <ol className="mt-2 list-decimal space-y-1 pl-4">
                    <li>Toca <strong>Conectar Gmail</strong>.</li>
                    <li>Elige la cuenta de Google que usara el hotel.</li>
                    <li>Acepta permisos de envio.</li>
                    <li>Vuelve al PMS y verifica que quede como conectado.</li>
                  </ol>
                  <p className="mt-2 text-[11px] text-sky-800">
                    Si la ventana de Google no vuelve sola al PMS, usa <strong>Tengo un codigo manual</strong> como respaldo.
                  </p>
                </div>
              )}

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
