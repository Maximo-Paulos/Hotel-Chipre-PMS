import { useCallback, useEffect, useState } from "react";

import { registerPushSubscription, unregisterPushSubscription } from "../api/notifications";
import { ApiError } from "../api/client";
import { useSession } from "../state/session";

import { isIOSDevice, isStandaloneDisplay } from "./useInstallPrompt";
import { useOnlineStatus } from "./useOnlineStatus";

const EVER_SUBSCRIBED_KEY = "chipre-push-ever-subscribed";
const VAPID_PUBLIC_KEY = (import.meta.env.VITE_WEB_PUSH_VAPID_PUBLIC_KEY as string | undefined) ?? "";

// Web Push subscription keys are base64url; PushManager.subscribe wants a
// Uint8Array applicationServerKey. Standard conversion, no library needed.
function urlBase64ToUint8Array(base64String: string): Uint8Array {
  const padding = "=".repeat((4 - (base64String.length % 4)) % 4);
  const base64 = (base64String + padding).replace(/-/g, "+").replace(/_/g, "/");
  const rawData = atob(base64);
  return Uint8Array.from(rawData, (char) => char.charCodeAt(0));
}

export type PushSubscriptionState = {
  supported: boolean;
  vapidConfigured: boolean;
  isIOS: boolean;
  isStandalone: boolean;
  // iOS Safari only allows requesting push permission from a PWA already
  // added to the Home Screen -- a plain browser tab silently no-ops the
  // permission prompt instead of erroring, so this must be checked and
  // surfaced *before* calling subscribe(), not discovered after a failure.
  iosNeedsInstall: boolean;
  permission: NotificationPermission | "unsupported";
  subscribed: boolean;
  // Browser has no subscription, but this device previously subscribed
  // (local flag) -- the subscription expired/was invalidated server- or
  // browser-side. Show "reconnect", not a silent no-op.
  needsReconnect: boolean;
  loading: boolean;
  error: string | null;
  isOnline: boolean;
};

export function usePushSubscription() {
  const { session } = useSession();
  const isOnline = useOnlineStatus();
  const supported =
    typeof navigator !== "undefined" && "serviceWorker" in navigator && "PushManager" in window && "Notification" in window;
  const isIOS = isIOSDevice();
  const isStandalone = isStandaloneDisplay();
  const iosNeedsInstall = isIOS && !isStandalone;

  const [permission, setPermission] = useState<NotificationPermission | "unsupported">(
    supported ? Notification.permission : "unsupported"
  );
  const [subscribed, setSubscribed] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const refreshSubscriptionState = useCallback(async () => {
    if (!supported) {
      setLoading(false);
      return;
    }
    setPermission(Notification.permission);
    try {
      const registration = await navigator.serviceWorker.getRegistration();
      const existing = await registration?.pushManager.getSubscription();
      setSubscribed(Boolean(existing));
    } catch {
      setSubscribed(false);
    } finally {
      setLoading(false);
    }
  }, [supported]);

  useEffect(() => {
    void refreshSubscriptionState();
  }, [refreshSubscriptionState]);

  const everSubscribed = (() => {
    try {
      return window.localStorage.getItem(EVER_SUBSCRIBED_KEY) === "1";
    } catch {
      return false;
    }
  })();
  const needsReconnect = supported && permission === "granted" && everSubscribed && !subscribed;

  const subscribe = useCallback(async () => {
    setError(null);
    if (!supported || iosNeedsInstall || !isOnline) return;
    if (!VAPID_PUBLIC_KEY) {
      setError("Las notificaciones push no están configuradas para este hotel todavía.");
      return;
    }
    setLoading(true);
    try {
      // On-demand register here (independent of main.tsx's PROD-only load-time
      // registration) so an explicit "activar push" click works even before
      // that first registration lands -- register() is idempotent, it just
      // returns the existing registration if one is already active.
      const registration = await navigator.serviceWorker.register("/sw.js");
      await navigator.serviceWorker.ready;
      const permissionResult = await Notification.requestPermission();
      setPermission(permissionResult);
      if (permissionResult !== "granted") {
        setLoading(false);
        return;
      }
      const subscription = await registration.pushManager.subscribe({
        userVisibleOnly: true,
        applicationServerKey: urlBase64ToUint8Array(VAPID_PUBLIC_KEY)
      });
      const json = subscription.toJSON();
      if (!json.keys?.p256dh || !json.keys?.auth) {
        throw new Error("El navegador no devolvió las claves de la suscripción push.");
      }
      await registerPushSubscription(
        { endpoint: subscription.endpoint, p256dh: json.keys.p256dh, auth: json.keys.auth },
        session
      );
      try {
        window.localStorage.setItem(EVER_SUBSCRIBED_KEY, "1");
      } catch {
        /* ignore storage unavailable */
      }
      setSubscribed(true);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo activar las notificaciones push.");
    } finally {
      setLoading(false);
    }
  }, [supported, iosNeedsInstall, isOnline, session]);

  const unsubscribe = useCallback(async () => {
    setError(null);
    if (!supported || !isOnline) return;
    setLoading(true);
    try {
      const registration = await navigator.serviceWorker.getRegistration();
      const existing = await registration?.pushManager.getSubscription();
      if (existing) {
        await unregisterPushSubscription(existing.endpoint, session);
        await existing.unsubscribe();
      }
      try {
        window.localStorage.removeItem(EVER_SUBSCRIBED_KEY);
      } catch {
        /* ignore storage unavailable */
      }
      setSubscribed(false);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "No se pudo desactivar las notificaciones push.");
    } finally {
      setLoading(false);
    }
  }, [supported, isOnline, session]);

  const state: PushSubscriptionState = {
    supported,
    vapidConfigured: Boolean(VAPID_PUBLIC_KEY),
    isIOS,
    isStandalone,
    iosNeedsInstall,
    permission,
    subscribed,
    needsReconnect,
    loading,
    error,
    isOnline
  };

  return { ...state, subscribe, unsubscribe };
}
