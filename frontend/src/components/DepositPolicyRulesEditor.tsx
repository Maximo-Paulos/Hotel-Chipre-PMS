import type { DepositPolicyRule } from "../api/depositPolicy";

type Props = {
  rules: DepositPolicyRule[];
  onChange: (rules: DepositPolicyRule[]) => void;
  testId?: string;
};

const baseInputClass = "mt-1 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm";

function bandDescription(rules: DepositPolicyRule[], index: number) {
  const rule = rules[index];
  const previousMaximum = index > 0 ? rules[index - 1].max_nights : 0;
  const startsAt = (previousMaximum ?? 0) + 1;
  if (rule.max_nights === null) return index === 0 ? "Todas las estadías" : `Desde ${startsAt} noches`;
  return startsAt === rule.max_nights ? `${startsAt} noche` : `${startsAt} a ${rule.max_nights} noches`;
}

function addRule(rules: DepositPolicyRule[]): DepositPolicyRule[] {
  const next = rules.map((rule) => ({ ...rule }));
  const lastIndex = next.length - 1;
  const previousMaximum = lastIndex > 0 ? next[lastIndex - 1].max_nights ?? 0 : 0;
  next[lastIndex].max_nights = Math.max(next[lastIndex].max_nights ?? previousMaximum + 1, previousMaximum + 1);
  next.push({ max_nights: null, calculation: "nights", value: 1 });
  return next;
}

function removeRule(rules: DepositPolicyRule[], index: number): DepositPolicyRule[] {
  const next = rules.filter((_, currentIndex) => currentIndex !== index).map((rule) => ({ ...rule }));
  if (next.length) next[next.length - 1].max_nights = null;
  return next;
}

export function DepositPolicyRulesEditor({ rules, onChange, testId }: Props) {
  return (
    <section className="space-y-3" data-testid={testId}>
      <div>
        <p className="text-sm font-semibold text-slate-800">Seña según duración de la estadía</p>
        <p className="mt-1 text-xs text-slate-600">
          Definí rangos en noches. Cada regla puede pedir un porcentaje del total o el valor de una cantidad de noches.
        </p>
      </div>
      {rules.map((rule, index) => (
        <div key={index} className="grid gap-3 rounded-lg border border-slate-200 bg-white p-3 md:grid-cols-[1fr_1.5fr_1fr_auto] md:items-end">
          <label className="text-xs font-semibold text-slate-700">
            Rango: {bandDescription(rules, index)}
            <span className="mt-1 block font-normal text-slate-500">Hasta noches (vacío = sin límite)</span>
            <input
              className={baseInputClass}
              type="number"
              min={index > 0 ? (rules[index - 1].max_nights ?? 0) + 1 : 1}
              max={3650}
              value={rule.max_nights ?? ""}
              aria-label={`Límite de noches de regla ${index + 1}`}
              onChange={(event) => {
                const value = event.target.value.trim();
                const next = rules.map((current) => ({ ...current }));
                next[index].max_nights = value ? Number.parseInt(value, 10) : null;
                onChange(next);
              }}
            />
          </label>
          <label className="text-xs font-semibold text-slate-700">
            Cómo calcular la seña
            <select
              className={baseInputClass}
              value={rule.calculation}
              aria-label={`Tipo de seña de regla ${index + 1}`}
              onChange={(event) => {
                const calculation = event.target.value as DepositPolicyRule["calculation"];
                const next = rules.map((current) => ({ ...current }));
                next[index].calculation = calculation;
                next[index].value = calculation === "percentage" ? Math.min(30, next[index].value || 30) : 1;
                onChange(next);
              }}
            >
              <option value="percentage">Porcentaje del total</option>
              <option value="nights">Cantidad de noches</option>
            </select>
          </label>
          <label className="text-xs font-semibold text-slate-700">
            {rule.calculation === "percentage" ? "Porcentaje (%)" : "Noches a señar"}
            <input
              className={baseInputClass}
              type="number"
              min={rule.calculation === "percentage" ? 0 : 1}
              max={rule.calculation === "percentage" ? 100 : 3650}
              step={rule.calculation === "percentage" ? 0.1 : 1}
              value={rule.value}
              aria-label={`Valor de seña de regla ${index + 1}`}
              onChange={(event) => {
                const next = rules.map((current) => ({ ...current }));
                next[index].value = Number(event.target.value || 0);
                onChange(next);
              }}
            />
          </label>
          <button
            type="button"
            disabled={rules.length === 1}
            className="min-h-10 rounded-lg border border-slate-300 px-3 py-2 text-xs font-semibold text-slate-700 disabled:opacity-40"
            aria-label={`Quitar regla ${index + 1}`}
            onClick={() => onChange(removeRule(rules, index))}
          >
            Quitar
          </button>
        </div>
      ))}
      <button
        type="button"
        disabled={rules.length >= 10}
        className="min-h-10 rounded-lg border border-slate-300 px-3 py-2 text-sm font-semibold text-slate-700 disabled:opacity-40"
        onClick={() => onChange(addRule(rules))}
      >
        Agregar rango de estadía
      </button>
    </section>
  );
}
