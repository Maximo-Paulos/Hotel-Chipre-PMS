import { useState } from "react";

import { completeWhatsAppChannel } from "../../api/whatsapp";
import { useWhatsAppCRM } from "../../hooks/useWhatsappCRM";
import { useSession } from "../../state/session";

/** Human-readable onboarding state; provider credentials never enter the browser. */
export function SettingsWhatsAppPage() {
  const { session } = useSession();
  const { channel } = useWhatsAppCRM();
  const [wabaId, setWabaId] = useState("");
  const [phoneNumberId, setPhoneNumberId] = useState("");
  const [displayName, setDisplayName] = useState("");
  const [displayPhone, setDisplayPhone] = useState("");
  const [message, setMessage] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const current = channel.data?.channel;

  const saveMetadata = async () => {
    if (!wabaId.trim() || !phoneNumberId.trim()) return;
    setSaving(true);
    setMessage(null);
    try {
      await completeWhatsAppChannel({
        waba_id: wabaId.trim(), phone_number_id: phoneNumberId.trim(),
        display_name: displayName.trim() || undefined, display_phone_number: displayPhone.trim() || undefined,
      }, session);
      await channel.refetch();
      setMessage("Conexión registrada. Falta ejecutar la prueba de mensaje en un entorno Meta autorizado.");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "No se pudo registrar la conexión.");
    } finally {
      setSaving(false);
    }
  };

  return (
    <div className="max-w-2xl space-y-4">
      <div><p className="text-xs uppercase tracking-wide text-slate-500">Integraciones</p><h1 className="text-2xl font-semibold text-slate-900">WhatsApp Business</h1><p className="text-sm text-slate-600">El hotel es dueño de su WABA y el PMS guarda solo metadatos operativos.</p></div>
      <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm">
        <p className="text-sm font-semibold">Estado: {channel.isLoading ? "cargando" : current?.status || channel.data?.status || "no conectado"}</p>
        <p className="mt-1 text-xs text-slate-600">Embedded Signup y los secretos se resuelven del lado servidor. Nunca pegues un access token aquí.</p>
        {current ? <p className="mt-3 text-sm text-slate-700">{current.display_name || "Número conectado"} {current.display_phone_number ? `· ${current.display_phone_number}` : ""}</p> : (
          <div className="mt-4 space-y-3">
            <p className="text-xs text-slate-600">Después de completar Embedded Signup, registra la respuesta metadata para iniciar la prueba controlada.</p>
            <input className="w-full rounded border px-3 py-2 text-sm" placeholder="WABA ID" value={wabaId} onChange={(event) => setWabaId(event.target.value)} />
            <input className="w-full rounded border px-3 py-2 text-sm" placeholder="Phone Number ID" value={phoneNumberId} onChange={(event) => setPhoneNumberId(event.target.value)} />
            <div className="grid gap-3 sm:grid-cols-2"><input className="rounded border px-3 py-2 text-sm" placeholder="Nombre visible (opcional)" value={displayName} onChange={(event) => setDisplayName(event.target.value)} /><input className="rounded border px-3 py-2 text-sm" placeholder="Número visible (opcional)" value={displayPhone} onChange={(event) => setDisplayPhone(event.target.value)} /></div>
            <button type="button" disabled={saving || !wabaId.trim() || !phoneNumberId.trim()} onClick={saveMetadata} className="rounded bg-brand-600 px-3 py-2 text-sm font-semibold text-white disabled:opacity-50">Registrar metadata</button>
          </div>
        )}
        {message && <p className="mt-3 text-sm" role="status">{message}</p>}
      </div>
    </div>
  );
}
