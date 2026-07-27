// ponytail: replaces window.confirm for destructive actions. window.confirm
// is a synchronous, chrome-owned dialog -- some mobile in-app browsers
// (WhatsApp/Instagram-style embedded WebViews) silently no-op JS dialogs
// instead of showing them, so a tap on "Eliminar" can do nothing with zero
// feedback. An in-page modal always renders regardless of the host browser.
// Same visual pattern as ManualOtaReservationModal.tsx.
type ConfirmDialogProps = {
  open: boolean;
  title: string;
  message: string;
  confirmLabel?: string;
  cancelLabel?: string;
  danger?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export default function ConfirmDialog({
  open,
  title,
  message,
  confirmLabel = "Confirmar",
  cancelLabel = "Cancelar",
  danger = true,
  onConfirm,
  onCancel
}: ConfirmDialogProps) {
  if (!open) return null;

  return (
    <div
      className="fixed inset-0 z-40 flex animate-fade-in items-center justify-center bg-slate-900/40 px-4 py-6"
      onClick={onCancel}
    >
      <div
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-message"
        className="w-full max-w-sm animate-scale-in rounded-xl border border-slate-200 bg-white p-5 shadow-xl"
        onClick={(event) => event.stopPropagation()}
      >
        <h2 id="confirm-dialog-title" className="text-base font-semibold text-slate-900">
          {title}
        </h2>
        <p id="confirm-dialog-message" className="mt-2 text-sm text-slate-600">
          {message}
        </p>
        <div className="mt-4 flex gap-2">
          <button
            type="button"
            onClick={onCancel}
            className="min-h-11 flex-1 rounded-lg border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-700 hover:bg-slate-50"
          >
            {cancelLabel}
          </button>
          <button
            type="button"
            autoFocus
            onClick={onConfirm}
            className={`min-h-11 flex-1 rounded-lg border px-3 py-2 text-sm font-semibold text-white ${
              danger ? "border-rose-600 bg-rose-600 hover:bg-rose-700" : "border-brand-600 bg-brand-600 hover:bg-brand-700"
            }`}
          >
            {confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
