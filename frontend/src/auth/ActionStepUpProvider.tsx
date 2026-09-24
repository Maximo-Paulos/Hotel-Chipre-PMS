import { useCallback, useEffect, useRef, useState, type FormEvent, type ReactNode } from "react";
import { useTranslation } from "react-i18next";

import {
  ApiError,
  apiFetch,
  setActionStepUpHandler,
  type ActionStepUpChallenge,
  type ActionStepUpTicket,
  type SessionLike
} from "../api/client";
import { useDialogA11y } from "../hooks/useDialogA11y";
import { useSession } from "../state/session";

type PendingStepUp = {
  id: number;
  challenge: ActionStepUpChallenge;
  session: SessionLike | null;
  resolve: (ticket: ActionStepUpTicket | null) => void;
  removeAbortListener?: () => void;
};

type ActionStepUpResponse = {
  ticket: string;
  scope?: "action" | "permission_admin_read";
  expires_in?: number;
};

const sameSessionSnapshot = (snapshot: SessionLike | null, current: SessionLike | null) => {
  const snapshotUserId = snapshot?.userId?.trim().toLowerCase() ?? "";
  const currentUserId = current?.userId?.trim().toLowerCase() ?? "";
  const snapshotToken = snapshot?.accessToken?.trim() ?? "";
  const currentToken = current?.accessToken?.trim() ?? "";
  const snapshotHotelId = snapshot?.hotelId;
  const currentHotelId = current?.hotelId;

  return Boolean(
    snapshotUserId &&
      currentUserId &&
      snapshotToken &&
      currentToken &&
      snapshotHotelId &&
      currentHotelId &&
      snapshotUserId === currentUserId &&
      snapshotHotelId === currentHotelId &&
      snapshotToken === currentToken
  );
};

export function ActionStepUpProvider({ children }: { children: ReactNode }) {
  const { t } = useTranslation();
  const { session } = useSession();
  const [activePrompt, setActivePrompt] = useState<PendingStepUp | null>(null);
  const [totpCode, setTotpCode] = useState("");
  const [errorMessage, setErrorMessage] = useState("");
  const [isSubmitting, setIsSubmitting] = useState(false);
  const codeInputRef = useRef<HTMLInputElement | null>(null);
  const activePromptRef = useRef<PendingStepUp | null>(null);
  const currentSessionRef = useRef<SessionLike>(session);
  const promptIdRef = useRef(0);
  const submitControllerRef = useRef<AbortController | null>(null);
  currentSessionRef.current = session;

  const settlePrompt = useCallback((ticket: ActionStepUpTicket | null) => {
    const pending = activePromptRef.current;
    if (!pending) return;

    activePromptRef.current = null;
    pending.removeAbortListener?.();
    const controller = submitControllerRef.current;
    submitControllerRef.current = null;
    controller?.abort();
    setActivePrompt(null);
    setTotpCode("");
    setErrorMessage("");
    setIsSubmitting(false);
    pending.resolve(ticket);
  }, []);

  const enqueuePrompt = useCallback(
    (challenge: ActionStepUpChallenge, session: SessionLike | null, signal?: AbortSignal) =>
      new Promise<ActionStepUpTicket | null>((resolve) => {
        if (signal?.aborted || !sameSessionSnapshot(session, currentSessionRef.current)) {
          resolve(null);
          return;
        }

        const pending: PendingStepUp = {
          id: ++promptIdRef.current,
          challenge,
          session,
          resolve
        };
        if (signal) {
          const onAbort = () => {
            if (activePromptRef.current === pending) settlePrompt(null);
          };
          signal.addEventListener("abort", onAbort, { once: true });
          pending.removeAbortListener = () => signal.removeEventListener("abort", onAbort);
        }
        activePromptRef.current = pending;
        setActivePrompt(pending);
        setTotpCode("");
        setErrorMessage("");
        setIsSubmitting(false);
      }),
    [settlePrompt]
  );

  const cancelPrompt = useCallback(() => settlePrompt(null), [settlePrompt]);
  const dialogRef = useDialogA11y(Boolean(activePrompt), cancelPrompt);

  useEffect(() => {
    const pending = activePromptRef.current;
    if (pending && !sameSessionSnapshot(pending.session, currentSessionRef.current)) settlePrompt(null);
  }, [activePrompt?.id, session.userId, session.hotelId, session.accessToken, settlePrompt]);

  useEffect(() => {
    if (activePrompt) codeInputRef.current?.focus();
  }, [activePrompt]);

  useEffect(() => {
    const unregister = setActionStepUpHandler(enqueuePrompt);
    return () => {
      unregister();
      submitControllerRef.current?.abort();
      submitControllerRef.current = null;
      const pending = activePromptRef.current;
      activePromptRef.current = null;
      pending?.removeAbortListener?.();
      pending?.resolve(null);
    };
  }, [enqueuePrompt]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    const pending = activePromptRef.current;
    const code = totpCode.trim();
    if (!pending || isSubmitting || !code) return;
    if (!sameSessionSnapshot(pending.session, currentSessionRef.current)) {
      settlePrompt(null);
      return;
    }

    const controller = new AbortController();
    submitControllerRef.current = controller;
    setIsSubmitting(true);
    setErrorMessage("");

    try {
      const result = await apiFetch<ActionStepUpResponse>("/api/auth/step-up", {
        method: "POST",
        session: pending.session ?? undefined,
        signal: controller.signal,
        data: {
          // The current FastAPI ActionStepUpRequest names the TOTP field `code`.
          code,
          permission_code: pending.challenge.permissionCode,
          method: pending.challenge.method,
          path: pending.challenge.path
        }
      });

      if (typeof result?.ticket !== "string" || !result.ticket) {
        throw new Error("Missing step-up ticket");
      }
      if (activePromptRef.current === pending) {
        if (!sameSessionSnapshot(pending.session, currentSessionRef.current)) {
          settlePrompt(null);
          return;
        }
        settlePrompt({
          ticket: result.ticket,
          scope: result.scope === "permission_admin_read" ? "permission_admin_read" : "action",
          expiresInSeconds: Number.isFinite(result.expires_in) ? (result.expires_in as number) : 120
        });
      }
    } catch (error) {
      if (!controller.signal.aborted && activePromptRef.current === pending) {
        if (error instanceof ApiError && error.status === 401) {
          setErrorMessage(
            t("auth.stepUp.invalidCode", {
              defaultValue: "El código no es válido o ya fue usado. Ingresá uno nuevo."
            })
          );
        } else if (error instanceof ApiError && error.status === 429) {
          setErrorMessage(
            t("auth.stepUp.rateLimited", {
              defaultValue: "Hubo demasiados intentos. Esperá un momento y probá de nuevo."
            })
          );
        } else {
          setErrorMessage(
            t("auth.stepUp.error", {
              defaultValue: "No se pudo completar la verificación. Revisá tu conexión y volvé a intentar."
            })
          );
        }
      }
    } finally {
      if (activePromptRef.current === pending) {
        setTotpCode("");
        setIsSubmitting(false);
      }
      if (submitControllerRef.current === controller) submitControllerRef.current = null;
    }
  };

  const titleId = `action-step-up-title-${activePrompt?.id ?? "closed"}`;
  const descriptionId = `action-step-up-description-${activePrompt?.id ?? "closed"}`;
  const inputId = `action-step-up-code-${activePrompt?.id ?? "closed"}`;
  const errorId = `action-step-up-error-${activePrompt?.id ?? "closed"}`;

  return (
    <>
      {children}
      {activePrompt ? (
        <div className="fixed inset-0 z-[100] flex items-center justify-center bg-slate-950/60 p-4">
          <div
            ref={dialogRef}
            role="dialog"
            aria-modal="true"
            aria-labelledby={titleId}
            aria-describedby={descriptionId}
            aria-busy={isSubmitting}
            tabIndex={-1}
            className="max-h-[calc(100dvh-2rem)] w-full max-w-md overflow-y-auto rounded-2xl bg-white p-6 shadow-2xl outline-none"
          >
            <h2 id={titleId} className="text-lg font-semibold text-slate-900">
              {t("auth.stepUp.title", { defaultValue: "Confirmá que sos vos" })}
            </h2>
            <p id={descriptionId} className="mt-2 text-sm leading-6 text-slate-600">
              {t("auth.stepUp.description", {
                defaultValue: "Esta acción sensible requiere una verificación adicional. Ingresá el código temporal de tu app autenticadora."
              })}
            </p>

            <form className="mt-5 space-y-5" onSubmit={handleSubmit}>
              <div>
                <label htmlFor={inputId} className="mb-1.5 block text-sm font-medium text-slate-800">
                  {t("auth.stepUp.codeLabel", { defaultValue: "Código de autenticación" })}
                </label>
                <input
                  ref={codeInputRef}
                  autoComplete="one-time-code"
                  autoCapitalize="off"
                  inputMode="numeric"
                  maxLength={64}
                  name="totp-code"
                  onChange={(event) => setTotpCode(event.currentTarget.value)}
                  placeholder={t("auth.stepUp.codePlaceholder", { defaultValue: "Ingresá tu código" })}
                  required
                  type="text"
                  value={totpCode}
                  id={inputId}
                  aria-invalid={Boolean(errorMessage)}
                  aria-describedby={errorMessage ? errorId : undefined}
                  spellCheck={false}
                  className="block w-full rounded-lg border border-slate-300 px-3 py-2.5 text-base text-slate-900 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-indigo-500 focus:ring-2 focus:ring-indigo-200"
                />
                {errorMessage ? (
                  <p id={errorId} role="alert" className="mt-2 text-sm text-red-700">
                    {errorMessage}
                  </p>
                ) : null}
              </div>

              <div className="flex flex-col-reverse gap-3 sm:flex-row sm:justify-end">
                <button
                  type="button"
                  onClick={cancelPrompt}
                  className="rounded-lg border border-slate-300 px-4 py-2.5 text-sm font-medium text-slate-700 transition hover:bg-slate-50 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2"
                >
                  {t("auth.stepUp.cancel", { defaultValue: "Cancelar" })}
                </button>
                <button
                  type="submit"
                  disabled={!totpCode.trim() || isSubmitting}
                  className="rounded-lg bg-indigo-600 px-4 py-2.5 text-sm font-semibold text-white transition hover:bg-indigo-700 focus:outline-none focus:ring-2 focus:ring-indigo-500 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-60"
                >
                  {isSubmitting
                    ? t("auth.stepUp.submitting", { defaultValue: "Verificando…" })
                    : t("auth.stepUp.submit", { defaultValue: "Verificar y continuar" })}
                </button>
              </div>
            </form>
          </div>
        </div>
      ) : null}
    </>
  );
}
