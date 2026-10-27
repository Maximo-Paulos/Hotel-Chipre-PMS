import { useTranslation } from "react-i18next";

import type { ActiveAllocationPolicy } from "../api/allocation";

type AllocationPolicySettingsProps = {
  policy: ActiveAllocationPolicy | undefined;
  isLoading: boolean;
  error: string | null;
};

export function AllocationPolicySettings({ policy, isLoading, error }: AllocationPolicySettingsProps) {
  const { t } = useTranslation("allocation");
  const version = policy?.version;
  const ignoredLegacyObjective = version?.constraints.legacy_objective_ignored;

  return (
    <section className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm sm:p-5" aria-labelledby="allocation-policy-title">
      <div className="flex flex-col gap-1 sm:flex-row sm:items-start sm:justify-between">
        <div>
          <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{t("policy.eyebrow")}</p>
          <h2 id="allocation-policy-title" className="mt-1 text-lg font-semibold text-slate-900">{t("policy.title")}</h2>
          <p className="mt-1 max-w-2xl text-sm text-slate-600">{t("policy.description")}</p>
        </div>
        {version ? <span className="mt-2 self-start rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-700 sm:mt-0">{t("policy.version", { version: version.version_number })}</span> : null}
      </div>

      {isLoading ? <p className="mt-4 text-sm text-slate-600" role="status">{t("policy.loading")}</p> : null}
      {error ? <p className="mt-4 rounded-lg border border-rose-200 bg-rose-50 p-3 text-sm text-rose-800" role="alert">{t("policy.loadFailed", { message: error })}</p> : null}

      {policy ? (
        <div className="mt-4 space-y-3">
          <div>
            <p className="text-xs font-semibold uppercase tracking-wide text-slate-500">{t("policy.objective")}</p>
            <p className="mt-1 text-sm font-medium text-slate-900">{t("policy.objectives.occupiedNights")}</p>
          </div>
          <p className="rounded-lg border border-sky-200 bg-sky-50 p-3 text-sm text-sky-900" role="note">
            {t("policy.assignmentObjectiveNote")}
          </p>
          {typeof ignoredLegacyObjective === "string" ? (
            <p className="rounded-lg border border-amber-200 bg-amber-50 p-3 text-sm text-amber-900" role="status">
              {t("policy.legacyObjectiveNormalized", { objective: ignoredLegacyObjective })}
            </p>
          ) : null}
        </div>
      ) : null}
    </section>
  );
}
