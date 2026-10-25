import { useEffect, useState, type FormEvent } from "react";
import { useTranslation } from "react-i18next";

import type { ActiveAllocationPolicy, AllocationObjective } from "../api/allocation";

type AllocationPolicySettingsProps = {
  policy: ActiveAllocationPolicy | undefined;
  isLoading: boolean;
  error: string | null;
  isSaving: boolean;
  onSave: (objective: AllocationObjective, revenueWeight: number) => Promise<unknown>;
};

export function AllocationPolicySettings({ policy, isLoading, error, isSaving, onSave }: AllocationPolicySettingsProps) {
  const { t } = useTranslation("allocation");
  const [objective, setObjective] = useState<AllocationObjective>("occupied_nights");
  const [revenuePercent, setRevenuePercent] = useState("50");
  const [saveError, setSaveError] = useState<string | null>(null);
  const [saveNotice, setSaveNotice] = useState<string | null>(null);
  const version = policy?.version;

  useEffect(() => {
    if (!version) return;
    setObjective(version.optimization_objective);
    const configuredWeight = version.combined_revenue_weight ?? version.weights.combined_revenue_weight ?? 0.5;
    setRevenuePercent(String(Math.round(configuredWeight * 100)));
  }, [version]);

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault();
    setSaveError(null);
    setSaveNotice(null);
    try {
      await onSave(objective, Number(revenuePercent) / 100);
      setSaveNotice(t("policy.saved"));
    } catch (reason) {
      setSaveError(reason instanceof Error ? reason.message : t("policy.saveFailed"));
    }
  };

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5" aria-labelledby="allocation-policy-title">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{t("policy.eyebrow")}</p>
          <h2 id="allocation-policy-title" className="mt-1 text-lg font-semibold text-slate-900">{t("policy.title")}</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">{t("policy.description")}</p>
        </div>
        {policy ? <span className="mt-2 self-start rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700 sm:mt-0">{t("policy.version", { version: policy.version.version_number })}</span> : null}
      </div>

      {isLoading ? <p className="mt-4 text-sm text-slate-600" role="status">{t("policy.loading")}</p> : null}
      {error ? <p className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">{t("policy.loadFailed", { message: error })}</p> : null}

      {policy ? (
        <form className="mt-4 grid gap-4 lg:grid-cols-[minmax(0,1fr)_minmax(14rem,0.7fr)_auto] lg:items-end" onSubmit={handleSubmit}>
          <label className="block text-sm font-medium text-slate-700">
            {t("policy.objective")}
            <select
              value={objective}
              onChange={(event) => setObjective(event.target.value as AllocationObjective)}
              className="mt-1.5 block min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200"
            >
              <option value="occupied_nights">{t("policy.objectives.occupiedNights")}</option>
              <option value="net_revenue">{t("policy.objectives.netRevenue")}</option>
              <option value="combined">{t("policy.objectives.combined")}</option>
            </select>
          </label>

          <label className={`block text-sm font-medium text-slate-700 ${objective === "combined" ? "" : "opacity-60"}`}>
            {t("policy.revenueWeight")}
            <div className="mt-1.5 flex items-center gap-2">
              <input
                type="number"
                min="0"
                max="100"
                step="1"
                inputMode="numeric"
                value={revenuePercent}
                onChange={(event) => setRevenuePercent(event.target.value)}
                disabled={objective !== "combined"}
                aria-describedby="allocation-revenue-weight-help"
                className="min-h-11 w-full rounded-lg border border-slate-300 bg-white px-3 py-2 text-sm text-slate-900 shadow-sm focus:border-brand-500 focus:outline-none focus:ring-2 focus:ring-brand-200 disabled:bg-slate-100"
              />
              <span aria-hidden="true">%</span>
            </div>
            <span id="allocation-revenue-weight-help" className="mt-1 block text-xs font-normal text-slate-500">{t("policy.revenueWeightHelp")}</span>
          </label>

          <button
            type="submit"
            disabled={isSaving || isLoading || !policy || (objective === "combined" && (!Number.isFinite(Number(revenuePercent)) || Number(revenuePercent) < 0 || Number(revenuePercent) > 100))}
            className="min-h-11 rounded-lg bg-slate-900 px-4 py-2 text-sm font-semibold text-white hover:bg-slate-700 focus:outline-none focus:ring-2 focus:ring-slate-400 focus:ring-offset-2 disabled:cursor-not-allowed disabled:opacity-50"
          >
            {isSaving ? t("policy.saving") : t("policy.save")}
          </button>

          {objective === "combined" ? (
            <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900 lg:col-span-3" role="note">
              {t("policy.combinedNote")}
            </p>
          ) : objective === "net_revenue" ? (
            <p className="rounded-lg border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900 lg:col-span-3" role="note">
              {t("policy.revenueCurrencyNote")}
            </p>
          ) : null}

          {saveError ? <p className="rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800 lg:col-span-3" role="alert">{saveError}</p> : null}
          {error && !saveError ? null : saveNotice ? <p className="rounded-lg border border-emerald-200 bg-emerald-50 p-3 text-sm text-emerald-800 lg:col-span-3" role="status">{saveNotice}</p> : null}
        </form>
      ) : null}
    </section>
  );
}
