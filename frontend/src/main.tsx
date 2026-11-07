import React, { Suspense, lazy, useEffect, useState } from "react";
import ReactDOM from "react-dom/client";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useTranslation } from "react-i18next";

import App from "./App";
import { ApiError } from "./api/client";
import "./i18n";
import "./styles/tailwind.css";
import { SessionProvider } from "./state/session";
import { createCacheBustedReloadUrl } from "./utils/routeLoadError.mjs";

declare const __APP_BUILD_SHA__: string;

function ServiceWorkerUpdateNotice() {
  const [updateAvailable, setUpdateAvailable] = useState(false);
  const { t } = useTranslation("common");

  useEffect(() => {
    if (!import.meta.env.PROD || !("serviceWorker" in navigator)) return undefined;

    const onMessage = (event: MessageEvent) => {
      if (
        event.data?.type === "HOTEL_CHIPRE_APP_UPDATE" &&
        typeof event.data.codeSha === "string" &&
        event.data.codeSha !== __APP_BUILD_SHA__
      ) {
        setUpdateAvailable(true);
      }
    };
    const checkForUpdate = () => {
      void navigator.serviceWorker.getRegistration().then((registration) => registration?.update()).catch(() => {});
    };
    const registerServiceWorker = () => {
      void navigator.serviceWorker
        .register("/sw.js", { updateViaCache: "none" })
        .then((registration) => {
          if (registration.waiting) setUpdateAvailable(true);
          void registration.update().catch(() => {});
        })
        .catch(() => {
          // A service-worker update must never block hotel operations.
        });
    };
    const onVisibilityChange = () => {
      if (document.visibilityState === "visible") checkForUpdate();
    };

    navigator.serviceWorker.addEventListener("message", onMessage);
    window.addEventListener("focus", checkForUpdate);
    document.addEventListener("visibilitychange", onVisibilityChange);
    const updateInterval = window.setInterval(checkForUpdate, 5 * 60 * 1000);
    if (document.readyState === "complete") registerServiceWorker();
    else window.addEventListener("load", registerServiceWorker, { once: true });

    return () => {
      navigator.serviceWorker.removeEventListener("message", onMessage);
      window.removeEventListener("focus", checkForUpdate);
      document.removeEventListener("visibilitychange", onVisibilityChange);
      window.clearInterval(updateInterval);
    };
  }, []);

  if (!updateAvailable) return null;

  return (
    <div
      role="status"
      aria-live="polite"
      className="fixed inset-x-0 top-0 z-[100] flex flex-wrap items-center justify-center gap-3 bg-slate-950 px-4 py-3 text-sm text-white shadow-lg"
    >
      <span>{t("appUpdate.description")}</span>
      <button
        type="button"
        onClick={() => window.location.replace(createCacheBustedReloadUrl(window.location.href))}
        className="min-h-10 rounded-md bg-white px-3 font-semibold text-slate-950 hover:bg-slate-100 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-white"
      >
        {t("appUpdate.reload")}
      </button>
    </div>
  );
}

const reloadMarker = new URL(window.location.href);
if (reloadMarker.searchParams.has("__app_reload")) {
  reloadMarker.searchParams.delete("__app_reload");
  window.history.replaceState(window.history.state, "", reloadMarker.toString());
}

const ReactQueryDevtools = import.meta.env.DEV
  ? lazy(() =>
      import("@tanstack/react-query-devtools").then((m) => ({ default: m.ReactQueryDevtools }))
    )
  : null;

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,
      refetchOnWindowFocus: false,
      // A 4xx response is a permanent client/permission/plan outcome. Retrying
      // it repeats the same SQL and payload work without changing the result.
      // Keep a single retry for transient network and server failures so a
      // degraded API does not multiply every active read several times.
      retry: (failureCount, error) => {
        // apiFetch maps its bounded GET deadline to 408. Treat that local
        // timeout as transient once, while keeping business/auth 4xx outcomes
        // and mutations out of the retry path.
        if (error instanceof ApiError && error.status === 408) return failureCount < 1;
        if (error instanceof ApiError && error.status >= 400 && error.status < 500) return false;
        return failureCount < 1;
      }
    }
  }
});

// Only register in production builds: the dev server's own HMR/module
// requests would otherwise get caught by the SW's fetch handler and served
// stale during local development.
if (import.meta.env.PROD && "serviceWorker" in navigator) {
  window.addEventListener("load", () => {
    navigator.serviceWorker.register("/sw.js").catch(() => {
      // Offline-shell caching is a progressive enhancement -- a failed
      // registration must never block the app from loading.
    });
  });
}

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <SessionProvider>
        <ServiceWorkerUpdateNotice />
        <App />
        {ReactQueryDevtools ? (
          <Suspense fallback={null}>
            <ReactQueryDevtools initialIsOpen={false} />
          </Suspense>
        ) : null}
      </SessionProvider>
    </QueryClientProvider>
  </React.StrictMode>
);
