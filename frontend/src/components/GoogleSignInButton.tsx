import { useEffect, useRef } from "react";

// Google Identity Services (GIS) ID-token flow: no backend redirect, Google
// hands the frontend a signed JWT directly and we forward it to
// POST /api/auth/google. Needs VITE_GOOGLE_CLIENT_ID (public, not secret) --
// see .env.example for the matching backend GOOGLE_CLIENT_ID and the
// authorized JavaScript origins to register in Google Cloud Console.
const CLIENT_ID = import.meta.env.VITE_GOOGLE_CLIENT_ID as string | undefined;
const GSI_SCRIPT_SRC = "https://accounts.google.com/gsi/client";

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

  useEffect(() => {
    if (!CLIENT_ID || !containerRef.current) return;
    let cancelled = false;

    loadGsiScript()
      .then(() => {
        if (cancelled || !containerRef.current || !window.google) return;
        window.google.accounts.id.initialize({
          client_id: CLIENT_ID,
          callback: (resp) => onCredential(resp.credential)
        });
        window.google.accounts.id.renderButton(containerRef.current, {
          type: "standard",
          theme: "outline",
          size: "large",
          width: 320,
          text: "continue_with"
        });
      })
      .catch(() => {
        // Google's script failed to load (offline, blocked, etc). The normal
        // email/password login still works, so this fails silently.
      });

    return () => {
      cancelled = true;
    };
  }, [onCredential]);

  if (!CLIENT_ID) return null;

  return <div ref={containerRef} data-testid="google-signin-button" className="flex justify-center" />;
}
