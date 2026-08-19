import { useEffect, useState } from "react";

// Chrome/Edge/Android fire this instead of letting the browser show its own
// install UI immediately -- capturing it is what lets us show our own
// "Instalar" button and call .prompt() on tap. Not in lib.dom.d.ts yet.
interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: "accepted" | "dismissed" }>;
}

const DISMISSED_KEY = "chipre-pwa-install-dismissed";

// iOS/iPadOS Safari: no `beforeinstallprompt`, no `navigator.standalone` on
// other platforms -- so "is this already an installed PWA" needs a
// browser-native check, not a captured event. Exported standalone (not just
// used internally) because usePushSubscription needs the same "already
// installed?" answer to decide whether push permission can even be
// requested on iOS.
export const isIOSDevice = (): boolean =>
  typeof navigator !== "undefined" && /iphone|ipad|ipod/i.test(navigator.userAgent);

export const isStandaloneDisplay = (): boolean => {
  if (typeof navigator !== "undefined" && (navigator as unknown as { standalone?: boolean }).standalone) return true;
  return typeof window !== "undefined" && window.matchMedia?.("(display-mode: standalone)").matches === true;
};

// ponytail: no offline-queue, no background sync -- just the minimal
// beforeinstallprompt capture the task asked for. iOS Safari never fires
// this event (no A2HS API), so canInstall stays false there; that's a
// platform limitation, not a bug here.
export function useInstallPrompt() {
  const [deferredEvent, setDeferredEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [dismissed, setDismissed] = useState(() => {
    try {
      return window.localStorage.getItem(DISMISSED_KEY) === "1";
    } catch {
      return false;
    }
  });

  useEffect(() => {
    const handler = (event: Event) => {
      event.preventDefault();
      setDeferredEvent(event as BeforeInstallPromptEvent);
    };
    window.addEventListener("beforeinstallprompt", handler);
    return () => window.removeEventListener("beforeinstallprompt", handler);
  }, []);

  const promptInstall = async () => {
    if (!deferredEvent) return;
    await deferredEvent.prompt();
    await deferredEvent.userChoice;
    setDeferredEvent(null);
  };

  const dismiss = () => {
    setDismissed(true);
    try {
      window.localStorage.setItem(DISMISSED_KEY, "1");
    } catch {
      // localStorage unavailable (private mode) -- dismissal just won't persist.
    }
  };

  return {
    canInstall: Boolean(deferredEvent) && !dismissed,
    promptInstall,
    dismiss,
    isIOS: isIOSDevice(),
    isStandalone: isStandaloneDisplay()
  };
}
