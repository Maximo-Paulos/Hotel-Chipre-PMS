import { useEffect, useRef } from "react";

const FOCUSABLE_SELECTOR =
  'a[href], button:not([disabled]), textarea:not([disabled]), input:not([disabled]), select:not([disabled]), [tabindex]:not([tabindex="-1"])';

// ponytail: one hook instead of repeating Escape/focus-trap/scroll-lock/
// viewport logic in every dialog/drawer component (ReservationDetailDrawer,
// ConfirmDialog, RestrictionOverrideModal, IntegrationHelpDrawer,
// ManualOtaReservationModal, the AppShell mobile nav panel, NotificationsPanel).
// Call it unconditionally (pass `open`, it no-ops while closed) and attach
// the returned ref to the dialog's outer, focusable panel element.
export function useDialogA11y(open: boolean, onClose: () => void) {
  const containerRef = useRef<HTMLDivElement | null>(null);
  const triggerRef = useRef<Element | null>(null);
  // ponytail: onClose is an inline closure in every caller, so it gets a new
  // identity on every parent re-render (e.g. typing in a form field inside
  // the dialog). Reading it via ref keeps the effect below from re-running
  // on those renders -- otherwise it steals focus back to the first
  // focusable element (the close button) after every keystroke.
  const onCloseRef = useRef(onClose);
  onCloseRef.current = onClose;

  useEffect(() => {
    if (!open) return;
    triggerRef.current = document.activeElement;

    const container = containerRef.current;
    const focusables = () =>
      container ? Array.from(container.querySelectorAll<HTMLElement>(FOCUSABLE_SELECTOR)) : [];

    (focusables()[0] ?? container)?.focus();

    const originalOverflow = document.body.style.overflow;
    document.body.style.overflow = "hidden";

    const handleKeyDown = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        event.preventDefault();
        onCloseRef.current();
        return;
      }
      if (event.key !== "Tab") return;
      const items = focusables();
      if (items.length === 0) return;
      const first = items[0];
      const last = items[items.length - 1];
      if (event.shiftKey && document.activeElement === first) {
        event.preventDefault();
        last.focus();
      } else if (!event.shiftKey && document.activeElement === last) {
        event.preventDefault();
        first.focus();
      }
    };

    // iOS Safari: the virtual keyboard shrinks the visual viewport without
    // resizing the layout viewport, so a fixed-position dialog can end up
    // with its focused input hidden behind the keyboard. Nudge the focused
    // field back into view once the viewport actually shrinks.
    const handleViewportResize = () => {
      const active = document.activeElement as HTMLElement | null;
      if (active && container?.contains(active)) {
        active.scrollIntoView({ block: "center" });
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    window.visualViewport?.addEventListener("resize", handleViewportResize);

    return () => {
      document.body.style.overflow = originalOverflow;
      document.removeEventListener("keydown", handleKeyDown);
      window.visualViewport?.removeEventListener("resize", handleViewportResize);
      (triggerRef.current as HTMLElement | null)?.focus?.();
    };
  }, [open]);

  return containerRef;
}
