import { useState } from "react";

import { Section, SectionHeading } from "../Section";
import { moduleGroups } from "../../../content/marketing";

/**
 * The correction to the old page, which sold five features out of roughly
 * thirty. Grouped by who does the work rather than by how the code is split,
 * because a hotelier reads the org chart, not the router.
 */
export function ModulesSection() {
  const [activeId, setActiveId] = useState(moduleGroups[0].id);
  const active = moduleGroups.find((group) => group.id === activeId) ?? moduleGroups[0];

  return (
    <Section id="sistema">
      <SectionHeading
        title="Un sistema, no seis suscripciones."
        lede="Cada área trabaja en su parte y todas escriben sobre los mismos datos. Nadie tiene que avisarle a nadie para que el estado quede al día."
      />

      <div className="mt-12 grid gap-8 lg:grid-cols-[minmax(0,0.32fr)_minmax(0,0.68fr)] lg:gap-14">
        <div role="tablist" aria-label="Áreas del hotel" className="flex flex-col">
          {moduleGroups.map((group) => {
            const selected = group.id === active.id;
            return (
              <button
                key={group.id}
                type="button"
                role="tab"
                id={`tab-${group.id}`}
                aria-selected={selected}
                aria-controls={`panel-${group.id}`}
                onClick={() => setActiveId(group.id)}
                className={`border-l-2 py-4 pl-5 pr-3 text-left transition duration-200 ease-rack ${
                  selected
                    ? "border-brass-500 bg-white"
                    : "border-ink-200 hover:border-ink-400 hover:bg-white/60"
                }`}
              >
                <span
                  className={`block font-display text-lg font-semibold ${
                    selected ? "text-ink-950" : "text-ink-600"
                  }`}
                >
                  {group.label}
                </span>
                <span className="mt-1 block text-sm leading-6 text-ink-500">{group.summary}</span>
              </button>
            );
          })}
        </div>

        <div
          role="tabpanel"
          id={`panel-${active.id}`}
          aria-labelledby={`tab-${active.id}`}
          className="grid gap-px overflow-hidden rounded-panel bg-ink-200 sm:grid-cols-2"
        >
          {active.modules.map((module, index) => (
            <article
              key={module.name}
              // An odd count would otherwise leave the grid's own background
              // showing through as an empty grey cell.
              className={`bg-white px-6 py-6 ${
                index === active.modules.length - 1 && active.modules.length % 2 === 1
                  ? "sm:col-span-2"
                  : ""
              }`}
            >
              <h3 className="font-display text-base font-semibold text-ink-950">{module.name}</h3>
              <p className="mt-2 text-sm leading-6 text-ink-600">{module.body}</p>
            </article>
          ))}
        </div>
      </div>
    </Section>
  );
}

export default ModulesSection;
