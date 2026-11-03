import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/services/api";
import type { DeveloperDetail } from "@/types/api";

export default function DeveloperDetailPage() {
  const { projectId, developerId } = useParams<{ projectId: string; developerId: string }>();
  const [dev, setDev] = useState<DeveloperDetail | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (developerId) api.getDeveloper(developerId).then(setDev);
  }, [developerId]);

  if (!dev) return <div className="text-slate-500 text-sm">Loading…</div>;

  const riskColor = { LOW: "text-risk-low", MODERATE: "text-risk-moderate", HIGH: "text-risk-high" }[
    dev.dependency_risk
  ] ?? "text-risk-critical";

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">{dev.display_name}</h1>
      {dev.primary_email && <div className="text-sm text-slate-500 -mt-4">{dev.primary_email}</div>}

      <div className="grid grid-cols-3 gap-4">
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none">
          <div className="text-xs text-slate-500 mb-1">Critical module ownership</div>
          <div className="text-2xl font-semibold">{dev.critical_ownership_count}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none">
          <div className="text-xs text-slate-500 mb-1">Single-owner modules</div>
          <div className="text-2xl font-semibold">{dev.single_owner_modules_count}</div>
        </div>
        <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none">
          <div className="text-xs text-slate-500 mb-1">Dependency risk</div>
          <div className={`text-2xl font-semibold ${riskColor}`}>{dev.dependency_risk}</div>
        </div>
      </div>

      <div>
        <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Repository-derived knowledge familiarity</div>
        <div className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-200 shadow-sm dark:border-slate-800 dark:bg-transparent dark:divide-slate-800 dark:shadow-none">
          {dev.modules
            .slice()
            .sort((a, b) => b.score - a.score)
            .map((m) => (
              <button
                key={m.module_id}
                onClick={() => navigate(`/projects/${projectId}/modules/${m.module_id}`)}
                className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-slate-100 dark:hover:bg-slate-900"
              >
                <span className="text-sm">{m.module_name}</span>
                <div className="flex items-center gap-2">
                  <div className="w-32 h-1.5 rounded-full bg-slate-200 overflow-hidden dark:bg-slate-900">
                    <div className="h-full bg-slate-400 dark:bg-slate-400" style={{ width: `${m.score}%` }} />
                  </div>
                  <span className="text-xs text-slate-500 w-10 text-right">{m.score.toFixed(0)}</span>
                </div>
              </button>
            ))}
          {dev.modules.length === 0 && <div className="px-4 py-3 text-sm text-slate-500">No module activity found.</div>}
        </div>
      </div>
    </div>
  );
}
