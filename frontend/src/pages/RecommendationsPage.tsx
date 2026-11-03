import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/services/api";
import type { Recommendation } from "@/types/api";

const SEVERITY_STYLE: Record<string, string> = {
  CRITICAL: "border-risk-critical/40 bg-risk-critical/10 text-risk-critical",
  HIGH: "border-risk-high/40 bg-risk-high/10 text-risk-high",
  MODERATE: "border-risk-moderate/40 bg-risk-moderate/10 text-risk-moderate",
};

export default function RecommendationsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [recs, setRecs] = useState<Recommendation[] | null>(null);

  useEffect(() => {
    if (projectId) api.getRecommendations(projectId).then(setRecs);
  }, [projectId]);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Recommendations</h1>
      {recs === null && <div className="text-slate-500 text-sm">Loading…</div>}
      {recs?.length === 0 && (
        <div className="text-slate-500 text-sm">
          No recommendations yet — run analysis from the Dashboard, or this project may not have any active
          risk findings.
        </div>
      )}
      <div className="space-y-3">
        {recs?.map((r) => (
          <div key={r.id} className={`rounded-xl border p-4 ${SEVERITY_STYLE[r.severity] ?? "border-slate-800"}`}>
            <div className="flex items-center gap-2 mb-1">
              <span className="text-xs font-semibold uppercase tracking-wide">{r.severity}</span>
            </div>
            <div className="text-sm font-medium text-slate-900 dark:text-slate-100">{r.title}</div>
            <div className="text-sm text-slate-600 dark:text-slate-400 mt-1">{r.description}</div>
          </div>
        ))}
      </div>
    </div>
  );
}
