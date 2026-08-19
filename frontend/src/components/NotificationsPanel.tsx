import { useDialogA11y } from "../hooks/useDialogA11y";

type Props = {
  open: boolean;
  onClose: () => void;
};

// ponytail: notification *content* is Task 9 (backend outbox + real feed).
// This is only the visible affordance the mobile shell needs today -- a
// bell/alerts button that opens something instead of doing nothing. Wire
// real data in here once Task 9 ships; no fake data in the meantime.
export function NotificationsPanel({ open, onClose }: Props) {
  const containerRef = useDialogA11y(open, onClose);
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-50 flex animate-fade-in items-center justify-center bg-slate-900/40 px-4 py-6"
      onClick={onClose}
    >
      <div
        ref={containerRef}
        tabIndex={-1}
        role="dialog"
        aria-modal="true"
        aria-labelledby="notifications-panel-title"
        className="w-full max-w-sm animate-scale-in rounded-xl border border-slate-200 bg-white p-5 shadow-xl outline-none"
        onClick={(event) => event.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <h2 id="notifications-panel-title" className="text-base font-semibold text-slate-900">
            Alertas
          </h2>
          <button
            type="button"
            onClick={onClose}
            aria-label="Cerrar alertas"
            className="inline-flex min-h-11 min-w-11 items-center justify-center rounded-lg text-lg leading-none text-slate-500 hover:bg-slate-100 hover:text-slate-800"
          >
            ×
          </button>
        </div>
        <p className="mt-3 text-sm text-slate-600">
          Todavía no hay notificaciones para mostrar acá. El centro de alertas en tiempo real llega en una próxima
          actualización.
        </p>
      </div>
    </div>
  );
}

export default NotificationsPanel;
