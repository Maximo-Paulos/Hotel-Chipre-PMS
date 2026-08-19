import cx from "clsx";
import { NavLink } from "react-router-dom";

export type BottomNavTab =
  | { kind: "link"; label: string; to: string }
  | { kind: "button"; label: string; onClick: () => void; testId?: string; active?: boolean; badge?: boolean };

type Props = {
  tabs: BottomNavTab[];
};

// Mobile-only (rendered `md:hidden` by the caller) tab bar. Desktop keeps
// the existing sidebar untouched -- this is purely an additional surface,
// not a replacement. `env(safe-area-inset-*)` keeps tabs clear of the
// home-indicator on notched phones (see index.html viewport-fit=cover).
export function BottomNav({ tabs }: Props) {
  if (tabs.length === 0) return null;

  return (
    <nav
      aria-label="Navegación principal móvil"
      className="fixed inset-x-0 bottom-0 z-30 flex border-t border-slate-200 bg-white/95 backdrop-blur pb-[env(safe-area-inset-bottom)] pl-[env(safe-area-inset-left)] pr-[env(safe-area-inset-right)] md:hidden"
    >
      {tabs.map((tab) => {
        const itemClass = ({ active }: { active: boolean }) =>
          cx(
            "flex min-h-[56px] flex-1 flex-col items-center justify-center gap-0.5 px-1 text-[11px] font-medium",
            active ? "text-brand-700" : "text-slate-600"
          );

        if (tab.kind === "link") {
          return (
            <NavLink key={tab.to} to={tab.to} className={({ isActive }) => itemClass({ active: isActive })}>
              <span className="truncate">{tab.label}</span>
            </NavLink>
          );
        }

        return (
          <button
            key={tab.label}
            type="button"
            onClick={tab.onClick}
            data-testid={tab.testId}
            className={cx("relative", itemClass({ active: Boolean(tab.active) }))}
          >
            {tab.badge && (
              <span aria-hidden="true" className="absolute right-[30%] top-1 h-2 w-2 rounded-full bg-rose-600" />
            )}
            <span className="truncate">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

export default BottomNav;
