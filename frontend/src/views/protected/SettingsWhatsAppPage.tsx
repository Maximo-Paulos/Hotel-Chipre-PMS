import { Navigate } from "react-router-dom";

/** Backwards-compatible route kept for saved links; Connections owns WhatsApp. */
export function SettingsWhatsAppPage() {
  return <Navigate to="/settings/connections" replace />;
}
