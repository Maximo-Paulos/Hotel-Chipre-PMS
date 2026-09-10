import { integrations, integrationsCaveat } from "../../../content/marketing";

/**
 * Stands in for the social proof we do not have. Real integrations a hotel
 * recognises beat invented logos, and the caveat underneath is deliberate:
 * a hotelier who catches one overstated claim stops believing the page.
 */
export function IntegrationsStrip() {
  return (
    <section className="border-y border-ink-100 bg-white">
      <div className="mx-auto w-full max-w-6xl px-5 py-12 sm:px-8 lg:px-10">
        <div className="grid gap-8 lg:grid-cols-[minmax(0,0.75fr)_minmax(0,1.25fr)] lg:gap-12">
          <p className="max-w-sm text-base leading-7 text-ink-700">
            Se conecta con lo que tu hotel ya usa para vender y cobrar.
          </p>
          <ul className="grid grid-cols-2 gap-x-6 gap-y-5 sm:grid-cols-3">
            {integrations.map((integration) => (
              <li key={integration.name}>
                <p className="font-display text-base font-semibold text-ink-900">{integration.name}</p>
                <p className="mt-1 text-sm leading-6 text-ink-500">{integration.detail}</p>
              </li>
            ))}
          </ul>
        </div>
        <p className="mt-10 max-w-3xl border-l-2 border-brass-400 pl-4 text-sm leading-7 text-ink-600">
          {integrationsCaveat}
        </p>
      </div>
    </section>
  );
}

export default IntegrationsStrip;
