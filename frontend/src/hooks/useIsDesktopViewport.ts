import { useEffect, useState } from "react";

// Matches Tailwind's `md` breakpoint (768px), the same cutoff every existing
// desktop/mobile split in this codebase uses (`hidden md:block` / `md:hidden`,
// see RateEditorMobileCards.tsx). Content that must differ by breakpoint (not
// just layout -- e.g. which task-based tab is mounted) can't be done with CSS
// alone, so this hook is the JS-side source of truth for that split: it keeps
// a single DOM copy of shared sections (StockPage/LaundryPage's existing
// forms/history/lists) and toggles which ones are mounted, instead of
// duplicating markup with the same ids/labels under `hidden`/`md:hidden`
// (which would break existing desktop-viewport Playwright specs that query
// those ids/labels page-wide).
const QUERY = "(min-width: 768px)";

export function useIsDesktopViewport(): boolean {
  const [isDesktop, setIsDesktop] = useState(() =>
    typeof window === "undefined" ? true : window.matchMedia(QUERY).matches
  );

  useEffect(() => {
    if (typeof window === "undefined") return;
    const mql = window.matchMedia(QUERY);
    const onChange = () => setIsDesktop(mql.matches);
    onChange();
    mql.addEventListener("change", onChange);
    return () => mql.removeEventListener("change", onChange);
  }, []);

  return isDesktop;
}
