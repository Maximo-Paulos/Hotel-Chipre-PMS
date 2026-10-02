import { useTranslation } from "react-i18next";

import { MfaSettingsCard } from "../../components/MfaSettingsCard";
import { useSession } from "../../state/session";

export function SettingsMySecurityPage() {
  const { t } = useTranslation("appshell");
  const { session } = useSession();

  return (
    <div className="space-y-6" data-testid="personal-security-page">
      <header>
        <p className="text-xs uppercase tracking-wide text-slate-500">{t("nav.sections.settings.title")}</p>
        <h1 className="text-balance text-2xl font-semibold tracking-tight text-slate-900 sm:text-3xl">
          {t("mySecurityPage.title")}
        </h1>
        <p className="text-sm text-slate-600">{t("mySecurityPage.description")}</p>
      </header>
      <MfaSettingsCard session={session} returnTo={null} onContinue={() => undefined} />
    </div>
  );
}
