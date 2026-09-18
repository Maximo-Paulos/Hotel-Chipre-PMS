import { useEffect, useRef, useState } from "react";

import { getAuthProviders } from "../api/auth";

// Google Identity Services (GIS) ID-token flow: no backend redirect, Google
// hands the frontend a signed JWT directly and we forward it to
// POST /api/auth/google. The public client ID comes from the backend's
// provider-capabilities endpoint so Vercel and Render cannot drift apart.
const GSI_SCRIPT_SRC = "https://accounts.google.com/gsi/client";
let initializedClientId: string | null = null;
let activeCredentialCallback: ((idToken: string) => void) | null = null;

type CredentialResponse = { credential: string };

declare global {
  interface Window {
    google?: {
      accounts: {
        id: {
          initialize: (config: { client_id: string; callback: (resp: CredentialResponse) => void }) => void;
          renderButton: (parent: HTMLElement, options: Record<string, unknown>) => void;
        };
      };
    };
  }
}

function loadGsiScript(): Promise<void> {
  if (window.google?.accounts?.id) return Promise.resolve();
  const existing = document.querySelector<HTMLScriptElement>(`script[src="${GSI_SCRIPT_SRC}"]`);
  if (existing) {
    return new Promise((resolve) => existing.addEventListener("load", () => resolve(), { once: true }));
  }
  return new Promise((resolve, reject) => {
    const script = document.createElement("script");
    script.src = GSI_SCRIPT_SRC;
    script.async = true;
    script.defer = true;
    script.onload = () => resolve();
    script.onerror = () => reject(new Error("No se pudo cargar Google Identity Services"));
    document.head.appendChild(script);
  });
}

export function GoogleSignInButton({ onCredential }: { onCredential: (idToken: string) => void }) {
  const containerRef = useRef<HTMLDivElement>(null);
  const credentialRef = useRef(onCredential);
  const [clientId, setClientId] = useState<string | null>(null);
  credentialRef.current = onCredential;

  useEffect(() => {
    let cancelled = false;
    getAuthProviders()
      .then((providers) => {
        if (!cancelled && providers.google.enabled && providers.google.client_id) {
          setClientId(providers.google.client_id);
        }
      })
      .catch(() => {
        // Keep password login available if the provider-capabilities endpoint
        // is temporarily unavailable.
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!clientId || !containerRef.current) return;
    let cancelled = false;
    const callback = (idToken: string) => credentialRef.current(idToken);
    activeCredentialCallback = callback;

    loadGsiScript()
      .then(() => {
        if (cancelled || !containerRef.current || !window.google) return;
        if (initializedClientId !== clientId) {
          window.google.accounts.id.initialize({
            client_id: clientId,
            callback: (resp) => activeCredentialCallback?.(resp.credential)
          });
          initializedClientId = clientId;
        }
        if (containerRef.current.childElementCount === 0) {
          window.google.accounts.id.renderButton(containerRef.current, {
            type: "standard",
            theme: "outline",
            size: "large",
            width: 320,
            text: "continue_with"
          });
        }
      })
      .catch(() => {
        // Google's script failed to load (offline, blocked, etc). The normal
        // email/password login still works, so this fails silently.
      });

    return () => {
      cancelled = true;
      if (activeCredentialCallback === callback) activeCredentialCallback = null;
    };
  }, [clientId]);

  if (!clientId) return null;

  return <div ref={containerRef} data-testid="google-signin-button" className="flex justify-center" />;
}
