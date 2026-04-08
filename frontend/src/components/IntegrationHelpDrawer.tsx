import { integrationHelp, type IntegrationHelp } from "../content/integrationHelp";

type Props = {
  provider: string | null;
  open: boolean;
  onClose: () => void;
};

export function IntegrationHelpDrawer({ provider, open, onClose }: Props) {
  const help: IntegrationHelp | undefined = provider
    ? integrationHelp.find((h) => h.provider === provider)
    : undefined;

  if (!open) return null;

  return (
    <div className="fixed inset-0 z-50 flex">
      <div className="flex-1 bg-black/30" onClick={onClose} />
      <div className="w-full max-w-lg bg-white shadow-xl border-l border-slate-200 flex flex-col">
        <div className="flex items-start justify-between border-b px-4 py-3">
          <div>
            <h3 className="text-lg font-semibold text-slate-900">{help ? help.title : "Guía de conexión"}</h3>
            <p className="text-xs text-slate-500">Pasos para conectar {help?.provider || "la integración"}.</p>
          </div>
          <button onClick={onClose} className="text-slate-500 hover:text-slate-800 text-lg leading-none" aria-label="Cerrar">
            ×
          </button>
        </div>
        <div className="flex-1 overflow-y-auto px-4 py-4 text-sm text-slate-700 space-y-4">
          {!help && <p>Seleccioná un proveedor para ver los pasos.</p>}
          {help && (
            <>
              <ol className="list-decimal list-inside space-y-2">
                {help.steps.map((step, idx) => (
                  <li key={idx}>{step}</li>
                ))}
              </ol>
              {help.tips && (
                <div className="rounded-md bg-slate-50 border border-slate-200 px-3 py-2">
                  <p className="text-xs font-semibold text-slate-600 mb-1">Tips y seguridad</p>
                  <ul className="list-disc list-inside space-y-1">
                    {help.tips.map((tip, idx) => (
                      <li key={idx}>{tip}</li>
                    ))}
                  </ul>
                </div>
              )}
              {help.docUrl && (
                <a
                  href={help.docUrl}
                  target="_blank"
                  rel="noreferrer"
                  className="inline-flex items-center rounded-lg border border-slate-200 px-3 py-2 text-xs font-semibold text-slate-700 hover:border-brand-400"
                >
                  Ver doc oficial
                </a>
              )}
            </>
          )}
        </div>
      </div>
    </div>
  );
}
