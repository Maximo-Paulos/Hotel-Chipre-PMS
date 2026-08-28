export type MarketingIconName =
  | "arrow-right"
  | "check"
  | "chevron-right"
  | "mail"
  | "message"
  | "phone"
  | "shield"
  | "sparkles";

const paths: Record<MarketingIconName, JSX.Element> = {
  "arrow-right": <path d="M5 12h14m-6-6 6 6-6 6" />,
  check: <path d="m5 12 4 4L19 6" />,
  "chevron-right": <path d="m9 18 6-6-6-6" />,
  mail: <><rect x="3" y="5" width="18" height="14" rx="2" /><path d="m3 7 9 6 9-6" /></>,
  message: <><path d="M20 11.5a7.5 7.5 0 0 1-8 7.5 8.6 8.6 0 0 1-3.3-.7L4 20l1.7-4.1A7.2 7.2 0 0 1 4.5 12 7.5 7.5 0 0 1 12 4.5a7.5 7.5 0 0 1 8 7Z" /><path d="M8.5 12h.01M12 12h.01M15.5 12h.01" /></>,
  phone: <path d="M7.5 4.5 5 5.8c-.6.3-.9 1-.7 1.7 1.5 5.3 4.9 8.7 10.2 10.2.7.2 1.4-.1 1.7-.7l1.3-2.5-3.2-1.8-1.1 1.4a12 12 0 0 1-4.5-4.5l1.4-1.1-1.8-3.2Z" />,
  shield: <><path d="M12 3 19 6v5c0 4.5-2.9 8.1-7 9-4.1-.9-7-4.5-7-9V6l7-3Z" /><path d="m9 12 2 2 4-4" /></>,
  sparkles: <><path d="m12 3 1.1 4.1L17 8.5l-3.9 1.4L12 14l-1.1-4.1L7 8.5l3.9-1.4L12 3Z" /><path d="m19 14 .6 2.4L22 17l-2.4.6L19 20l-.6-2.4L16 17l2.4-.6L19 14ZM5 14l.5 1.5L7 16l-1.5.5L5 18l-.5-1.5L3 16l1.5-.5L5 14Z" /></>
};

export function MarketingIcon({ name, size = 18, className = "" }: { name: MarketingIconName; size?: number; className?: string }) {
  return (
    <svg
      aria-hidden="true"
      focusable="false"
      width={size}
      height={size}
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth="1.8"
      strokeLinecap="round"
      strokeLinejoin="round"
      className={className}
    >
      {paths[name]}
    </svg>
  );
}
