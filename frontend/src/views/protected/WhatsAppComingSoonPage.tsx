export function WhatsAppComingSoonPage() {
  return (
    <main className="mx-auto max-w-2xl space-y-4">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">Integraciones</p>
        <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">
          WhatsApp Business
        </h1>
      </header>
      <section
        aria-label="WhatsApp próximamente"
        className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm"
      >
        <span className="inline-flex rounded-full bg-amber-100 px-3 py-1 text-xs font-semibold text-amber-900">
          Próximamente
        </span>
        <p className="mt-3 text-sm leading-6 text-slate-700">
          La integración de WhatsApp sigue en desarrollo. Por ahora no se pueden conectar cuentas,
          atender conversaciones ni crear reservas desde WhatsApp en el PMS.
        </p>
      </section>
    </main>
  );
}
