const COLORS: Record<string, string> = {
  LOW: "bg-risk-low/15 text-risk-low border-risk-low/40",
  MODERATE: "bg-risk-moderate/15 text-risk-moderate border-risk-moderate/40",
  HIGH: "bg-risk-high/15 text-risk-high border-risk-high/40",
  CRITICAL: "bg-risk-critical/15 text-risk-critical border-risk-critical/40",
};

export default function RiskBadge({ level }: { level: string | null | undefined }) {
  if (!level) return <span className="text-slate-500 text-xs">—</span>;
  const cls = COLORS[level] ?? "bg-slate-500/15 text-slate-500 border-slate-500/40";
  return (
    <span className={`inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-medium ${cls}`}>
      {level}
    </span>
  );
}
