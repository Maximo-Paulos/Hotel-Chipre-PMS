import { useEffect, useId, useRef, useState } from "react";
import { createPortal } from "react-dom";

type InfoTipProps = {
  content: React.ReactNode;
  label?: string;
};

type PopoverPosition = {
  top: number;
  left: number;
};

const POPOVER_WIDTH = 360;

export function InfoTip({ content, label = "Más información" }: InfoTipProps) {
  const [open, setOpen] = useState(false);
  const [position, setPosition] = useState<PopoverPosition | null>(null);
  const buttonRef = useRef<HTMLButtonElement | null>(null);
  const popoverRef = useRef<HTMLDivElement | null>(null);
  const popoverId = useId();

  useEffect(() => {
    if (!open) {
      return undefined;
    }

    const updatePosition = () => {
      const rect = buttonRef.current?.getBoundingClientRect();
      if (!rect) {
        return;
      }

      const viewportWidth = window.innerWidth;
      const nextLeft = Math.min(
        Math.max(12, rect.left + rect.width / 2 - POPOVER_WIDTH / 2),
        viewportWidth - POPOVER_WIDTH - 12
      );

      setPosition({
        top: rect.bottom + 10,
        left: nextLeft
      });
    };

    const handlePointer = (event: MouseEvent) => {
      const target = event.target as Node;
      if (buttonRef.current?.contains(target) || popoverRef.current?.contains(target)) {
        return;
      }
      setOpen(false);
    };

    const handleEscape = (event: KeyboardEvent) => {
      if (event.key === "Escape") {
        setOpen(false);
      }
    };

    updatePosition();
    window.addEventListener("resize", updatePosition);
    window.addEventListener("scroll", updatePosition, true);
    document.addEventListener("mousedown", handlePointer);
    document.addEventListener("keydown", handleEscape);

    return () => {
      window.removeEventListener("resize", updatePosition);
      window.removeEventListener("scroll", updatePosition, true);
      document.removeEventListener("mousedown", handlePointer);
      document.removeEventListener("keydown", handleEscape);
    };
  }, [open]);

  return (
    <>
      <button
        ref={buttonRef}
        type="button"
        aria-label={label}
        aria-describedby={open ? popoverId : undefined}
        onClick={() => setOpen((current) => !current)}
        className="inline-flex h-5 w-5 items-center justify-center rounded-full border border-slate-400 text-[11px] font-semibold text-slate-200 transition hover:border-white hover:text-white"
      >
        i
      </button>
      {open && position
        ? createPortal(
            <div
              ref={popoverRef}
              id={popoverId}
              role="tooltip"
              className="fixed z-[70] w-[360px] max-w-[calc(100vw-24px)] rounded-xl border border-slate-200 bg-white p-3 text-left text-xs leading-5 text-slate-700 shadow-2xl"
              style={{ top: position.top, left: position.left }}
            >
              {content}
            </div>,
            document.body
          )
        : null}
    </>
  );
}
