import cx from "clsx";
import { NavLink } from "react-router-dom";

export type BottomNavTab =
  | { kind: "link"; label: string; to: string; icon: BottomNavIcon }
  | {
      kind: "button";
      label: string;
      onClick: () => void;
      icon: BottomNavIcon;
      testId?: string;
      active?: boolean;
      badge?: boolean;
      prominent?: boolean;
      controlsId?: string;
    };

export type BottomNavIcon =
  | "calendar"
  | "reservations"
  | "guests"
  | "rooms"
  | "cleaning"
  | "tasks"
  | "cash"
  | "laundry"
  | "more"
  | "plus";

type Props = {
  tabs: BottomNavTab[];
  menuOpen?: boolean;
};

function TabIcon({ name, active }: { name: BottomNavIcon; active: boolean }) {
  const iconClass = name === "plus" ? "text-white" : active ? "text-brand-700" : "text-slate-500";

  return (
    <svg
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={`h-5 w-5 shrink-0 ${iconClass}`}
      aria-hidden="true"
    >
      {name === "calendar" && (
        <>
          <rect x="3" y="5" width="18" height="16" rx="2" />
          <path d="M16 3v4M8 3v4M3 10h18" />
          <path d="M8 14h.01M12 14h.01M16 14h.01M8 17h.01M12 17h.01" />
        </>
      )}
      {name === "reservations" && (
        <>
          <rect x="5" y="4" width="14" height="17" rx="2" />
          <path d="M9 4.5V3h6v1.5M9 10h6M9 14h6M9 18h3" />
        </>
      )}
      {name === "guests" && (
        <>
          <path d="M16 21v-2a4 4 0 0 0-4-4H8a4 4 0 0 0-4 4v2" />
          <circle cx="10" cy="7" r="4" />
          <path d="M20 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75" />
        </>
      )}
      {name === "rooms" && (
        <>
          <path d="M3 20V8l9-5 9 5v12" />
          <path d="M3 12h18M7 20v-5h10v5M7 8h.01M17 8h.01" />
        </>
      )}
      {name === "cleaning" && (
        <>
          <path d="m4 20 8-8M14 4l6 6M12 12l4 4M4 20h6" />
          <path d="m14 4 2-2 6 6-2 2" />
        </>
      )}
      {name === "tasks" && (
        <>
          <rect x="4" y="3" width="16" height="18" rx="2" />
          <path d="m8 9 1.5 1.5L12 8M14 9h2M8 15l1.5 1.5L12 14M14 15h2" />
        </>
      )}
      {name === "cash" && (
        <>
          <rect x="3" y="5" width="18" height="14" rx="2" />
          <circle cx="12" cy="12" r="3" />
          <path d="M7 9h.01M17 15h.01" />
        </>
      )}
      {name === "laundry" && (
        <>
          <path d="M4 8h16l-1 12H5L4 8Z" />
          <path d="M3 5c1.5 0 1.5 2 3 2s1.5-2 3-2 1.5 2 3 2 1.5-2 3-2 1.5 2 3 2 1.5-2 3-2" />
          <path d="M8 12c1.4 2 2.7 2 4 0s2.7-2 4 0" />
        </>
      )}
      {name === "more" && (
        <>
          <circle cx="5" cy="12" r="1" />
          <circle cx="12" cy="12" r="1" />
          <circle cx="19" cy="12" r="1" />
        </>
      )}
      {name === "plus" && <path d="M12 5v14M5 12h14" />}
    </svg>
  );
}

// Mobile-only (rendered `md:hidden` by the caller) tab bar. Desktop keeps
// the existing sidebar untouched -- this is purely an additional surface,
// not a replacement. `env(safe-area-inset-*)` keeps tabs clear of the
// home-indicator on notched phones (see index.html viewport-fit=cover).
export function BottomNav({ tabs, menuOpen = false }: Props) {
  if (tabs.length === 0) return null;

  return (
    <nav
      aria-label="Navegación principal móvil"
      className="fixed inset-x-0 bottom-0 z-30 flex border-t border-ink-100 bg-paper-raised pb-[max(env(safe-area-inset-bottom),0.5rem)] pl-[env(safe-area-inset-left)] pr-[env(safe-area-inset-right)] shadow-[0_-4px_16px_rgba(7,26,34,0.06)] md:hidden"
    >
      {tabs.map((tab) => {
        const itemClass = ({ active }: { active: boolean }) =>
          cx(
            "flex min-h-16 min-w-0 flex-1 flex-col items-center justify-center gap-1 px-0.5 text-[10px] font-semibold leading-3",
            active ? "text-ink-800" : "text-slate-600",
          );

        if (tab.kind === "link") {
          return (
            <NavLink
              key={tab.to}
              to={tab.to}
              className={({ isActive }) => itemClass({ active: isActive })}
              data-testid={`bottom-nav-${tab.to.replace(/\//g, "-").replace(/^-/, "")}`}
              aria-label={tab.label}
            >
              {({ isActive }) => (
                <>
                  <span
                    className={cx(
                      "grid h-8 w-10 place-items-center rounded-xl",
                      isActive && "bg-brand-100",
                    )}
                  >
                    <TabIcon name={tab.icon} active={isActive} />
                  </span>
                  <span className="w-full max-w-full whitespace-normal break-words px-0.5 text-center leading-3">
                    {tab.label}
                  </span>
                </>
              )}
            </NavLink>
          );
        }

        return (
          <button
            key={tab.label}
            type="button"
            onClick={tab.onClick}
            data-testid={tab.testId}
            className={cx(
              "relative",
              tab.prominent
                ? "z-10 flex min-h-16 min-w-0 flex-1 flex-col items-center justify-end gap-1 px-0.5 pb-1 text-[10px] font-semibold leading-3 text-slate-700"
                : itemClass({ active: Boolean(tab.active) }),
            )}
            aria-label={tab.label}
            aria-haspopup="dialog"
            aria-expanded={Boolean(tab.active ?? menuOpen)}
            aria-controls={tab.controlsId}
          >
            {tab.prominent ? (
              <span className="absolute -top-3 left-1/2 grid h-[52px] w-[52px] -translate-x-1/2 place-items-center rounded-full bg-brand-600 text-white shadow-raise ring-4 ring-paper-raised">
                <TabIcon name={tab.icon} active={false} />
              </span>
            ) : (
              <span
                className={cx(
                  "grid h-8 w-10 place-items-center rounded-xl",
                  (tab.active ?? menuOpen) && "bg-brand-100",
                )}
              >
                <TabIcon
                  name={tab.icon}
                  active={Boolean(tab.active ?? menuOpen)}
                />
              </span>
            )}
            {tab.badge && (
              <span
                aria-hidden="true"
                className="absolute right-[30%] top-1 h-2 w-2 rounded-full bg-rose-600"
              />
            )}
            <span className="max-w-full truncate px-0.5">{tab.label}</span>
          </button>
        );
      })}
    </nav>
  );
}

export default BottomNav;
