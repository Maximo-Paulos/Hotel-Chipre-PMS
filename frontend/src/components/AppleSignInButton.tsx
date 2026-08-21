import { useEffect, useState } from "react";

const CLIENT_ID = import.meta.env.VITE_APPLE_CLIENT_ID as string | undefined;
const REDIRECT_URI = import.meta.env.VITE_APPLE_REDIRECT_URI as string | undefined;
const API_BASE =
  (import.meta.env.VITE_API_URL as string | undefined)?.replace(/\/$/, "") ||
  "http://127.0.0.1:8040/api";
const EFFECTIVE_REDIRECT_URI = REDIRECT_URI || `${API_BASE}/auth/apple/callback`;
const APPLE_SCRIPT_SRC = "https://appleid.cdn-apple.com/appleid/auth.init.js";

type AppleAuthorization = { id_token: string };
type AppleSignInResult = {
  authorization: AppleAuthorization;
  user?: { name?: { firstName?: string; lastName?: string } };
};

declare global {
  interface Window {
    AppleID?: {
      auth: {
        init: (config: {
          clientId: string;
          scope: "name email";
          redirectURI: string;
          usePopup: boolean;
          nonce?: string;
        }) => void;
        signIn: () => Promise<AppleSignInResult>;
      };
    };
  }
}

function loadAppleScript(): Promise<void> {
  if (window.AppleID?.auth) return Promise.resolve();
  const existing = document.querySelector<HTMLScriptElement>(`script[src="${APPLE_SCRIPT_SRC}"]`);
  if (existing) {
    return new Promise((resolve, reject) => {
      if (window.AppleID?.auth) {
        resolve();
        return;
      }
      existing.addEventListener("load", () => resolve(), { once: true });
      existing.addEventListener("error", () => reject(new Error("No se pudo cargar Apple Sign In")), { once: true });
    });
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = APPLE_SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("No se pudo cargar Apple Sign In"));
    document.head.appendChild(script);
  });
}

export function AppleSignInButton({
  disabled,
  onCredential
}: {
  disabled?: boolean;
  onCredential: (idToken: string, nonce: string, user?: AppleSignInResult["user"]) => void;
}) {
  const [ready, setReady] = useState(false);

  useEffect(() => {
    if (!CLIENT_ID) return;
    let cancelled = false;
    loadAppleScript()
      .then(() => {
        const appleAuth = window.AppleID?.auth;
        if (cancelled || !appleAuth) return;
        appleAuth.init({
          clientId: CLIENT_ID,
          scope: "name email",
          redirectURI: EFFECTIVE_REDIRECT_URI,
          usePopup: true
        });
        setReady(true);
      })
      .catch(() => setReady(false));
    return () => {
      cancelled = true;
    };
  }, []);

  if (!CLIENT_ID) return null;

  const handleClick = async () => {
    const appleAuth = window.AppleID?.auth;
    if (!ready || disabled || !appleAuth) return;
    const nonce = crypto.randomUUID();
    appleAuth.init({
      clientId: CLIENT_ID,
      scope: "name email",
      redirectURI: EFFECTIVE_REDIRECT_URI,
      usePopup: true,
      nonce
    });
    const result = await appleAuth.signIn();
    onCredential(result.authorization.id_token, nonce, result.user);
  };

  return (
    <button
      type="button"
      onClick={() => void handleClick().catch(() => undefined)}
      disabled={disabled || !ready}
      className="flex w-full items-center justify-center gap-2 rounded-lg bg-black px-3 py-2 text-sm font-semibold text-white shadow-sm hover:bg-slate-800 disabled:opacity-50"
      data-testid="apple-signin-button"
    >
      <span aria-hidden="true" className="text-lg leading-none"></span>
      Continuar con Apple
    </button>
  );
}
