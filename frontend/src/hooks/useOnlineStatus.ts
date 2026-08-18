import { useEffect, useState } from "react";

// ponytail: no existing navigator.onLine usage in this codebase to reuse
// (checked AppShell.tsx's "offline" banner -- that's backend-reachability,
// not network connectivity) -- this is the minimal browser-native check.
export function useOnlineStatus(): boolean {
  const [isOnline, setIsOnline] = useState(() => (typeof navigator === "undefined" ? true : navigator.onLine));

  useEffect(() => {
    if (typeof window === "undefined") return;
    const goOnline = () => setIsOnline(true);
    const goOffline = () => setIsOnline(false);
    window.addEventListener("online", goOnline);
    window.addEventListener("offline", goOffline);
    return () => {
      window.removeEventListener("online", goOnline);
      window.removeEventListener("offline", goOffline);
    };
  }, []);

  return isOnline;
}
