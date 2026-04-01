import React from "react";

type StatCardProps = {
  label: string;
  value: number | string;
  helper?: string;
  tone?: "default" | "success" | "danger" | "info";
};

const toneClasses: Record<NonNullable<StatCardProps["tone"]>, string> = {
  default: "border-slate-200 bg-white",
  success: "border-emerald-200 bg-emerald-50",
  danger: "border-rose-200 bg-rose-50",
  info: "border-sky-200 bg-sky-50"
};

export function StatCard({ label, value, helper, tone = "default" }: StatCardProps) {
  return (
    <div className={`rounded-lg border p-4 shadow-sm ${toneClasses[tone]}`}>
      <p className="text-xs uppercase tracking-wide text-slate-500">{label}</p>
      <p className="text-2xl font-semibold text-slate-900">{value}</p>
      {helper && <p className="text-xs text-slate-500">{helper}</p>}
    </div>
  );
}

export default StatCard;
