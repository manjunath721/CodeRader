import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/services/api";
import type { ModuleDetail } from "@/types/api";
import RiskBadge from "@/components/RiskBadge";

const FACTOR_LABELS: Record<string, string> = {
  knowledge_concentration: "Knowledge concentration",
  bus_factor_risk: "Bus factor risk",
  documentation_risk: "Documentation risk",
  complexity_risk: "Complexity risk",
  change_frequency_risk: "Change frequency risk",
  dependency_risk: "Dependency risk",
};

export default function ModuleDetailPage() {
  const { projectId, moduleId } = useParams<{ projectId: string; moduleId: string }>();
  const [module, setModule] = useState<ModuleDetail | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (moduleId) api.getModule(moduleId).then(setModule);
  }, [moduleId]);

  if (!module) return <div className="text-slate-500 text-sm">Loading…</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center gap-3">
        <h1 className="text-xl font-semibold">{module.name}</h1>
        <RiskBadge level={module.risk_level} />
        {module.is_critical_knowledge_area && (
          <span className="rounded-full border border-risk-critical/40 bg-risk-critical/10 text-risk-critical px-2.5 py-0.5 text-xs">
            CRITICAL KNOWLEDGE AREA
          </span>
        )}
      </div>
      <div className="text-sm text-slate-500 -mt-4">{module.path_prefix}</div>

      <div className="grid grid-cols-4 gap-4">
        <Stat label="Risk score" value={module.risk_score ?? "—"} />
        <Stat label="Bus factor" value={module.bus_factor ?? "—"} />
        <Stat label="Knowledge concentration" value={module.concentration_pct != null ? `${module.concentration_pct}%` : "—"} />
        <Stat label="Documentation" value={`${Math.round(module.documentation_score * 100)}%`} />
      </div>

      {module.risk_factors && (
        <div>
          <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Why this risk score — factor breakdown</div>
          <div className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-200 shadow-sm dark:border-slate-800 dark:bg-transparent dark:divide-slate-800 dark:shadow-none">
            {Object.entries(module.risk_factors.values).map(([key, value]) => (
              <div key={key} className="flex items-center justify-between px-4 py-2.5">
                <span className="text-sm text-slate-400">{FACTOR_LABELS[key] ?? key}</span>
                <div className="flex items-center gap-3">
                  <div className="w-40 h-1.5 rounded-full bg-slate-200 overflow-hidden dark:bg-slate-900">
                    <div className="h-full bg-slate-400" style={{ width: `${value * 100}%` }} />
                  </div>
                  <span className="text-xs text-slate-500 w-16 text-right">
                    weight {(module.risk_factors!.weights[key] * 100).toFixed(0)}%
                  </span>
                </div>
              </div>
            ))}
          </div>
        </div>
      )}

      <div>
          <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Knowledge distribution</div>
          <div className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-200 shadow-sm dark:border-slate-800 dark:bg-transparent dark:divide-slate-800 dark:shadow-none">
          {module.knowledge_distribution.map((k) => (
            <button
              key={k.developer_id}
              onClick={() => navigate(`/projects/${projectId}/developers/${k.developer_id}`)}
              className="w-full flex items-center justify-between px-4 py-2.5 text-left hover:bg-slate-100 dark:hover:bg-slate-900"
            >
              <span className="text-sm">{k.developer_name}</span>
              <div className="flex items-center gap-2">
                <div className="w-32 h-1.5 rounded-full bg-slate-200 overflow-hidden dark:bg-slate-900">
                  <div className="h-full bg-slate-400" style={{ width: `${k.score}%` }} />
                </div>
                <span className="text-xs text-slate-500 w-10 text-right">{k.score.toFixed(0)}</span>
              </div>
            </button>
          ))}
          {module.knowledge_distribution.length === 0 && (
            <div className="px-4 py-3 text-sm text-slate-500">No contributors found.</div>
          )}
        </div>
      </div>

      <div>
          <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Repository-derived backup candidates</div>
          <div className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-200 shadow-sm dark:border-slate-800 dark:bg-transparent dark:divide-slate-800 dark:shadow-none">
          {module.backup_candidates.map((c) => (
            <div key={c.developer_id} className="px-4 py-2.5">
              <div className="flex items-center justify-between">
                <span className="text-sm">{c.developer_name}</span>
                <span className="text-sm font-medium">{c.compatibility}% compatibility</span>
              </div>
              <div className="text-xs text-slate-500 mt-0.5">{c.reason}</div>
            </div>
          ))}
          {module.backup_candidates.length === 0 && (
            <div className="px-4 py-3 text-sm text-slate-500">No backup candidates identified.</div>
          )}
        </div>
      </div>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none">
      <div className="text-xs text-slate-500 mb-1">{label}</div>
      <div className="text-2xl font-semibold">{value}</div>
    </div>
  );
}
