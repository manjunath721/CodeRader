import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/services/api";
import type { ModuleSummary } from "@/types/api";
import RiskBadge from "@/components/RiskBadge";
import { Box } from "lucide-react";

export default function ModulesPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [modules, setModules] = useState<ModuleSummary[] | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (projectId) api.listModules(projectId).then(setModules);
  }, [projectId]);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Modules</h1>
      {modules === null && <div className="text-slate-500 text-sm">Loading…</div>}
      {modules?.length === 0 && (
        <div className="text-slate-500 text-sm">No modules detected yet — run analysis from the Dashboard.</div>
      )}
      <div className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-200 shadow-sm dark:border-slate-800 dark:bg-transparent dark:divide-slate-800 dark:shadow-none">
        {modules
          ?.slice()
          .sort((a, b) => (b.risk_score ?? 0) - (a.risk_score ?? 0))
          .map((m) => (
            <button
              key={m.id}
              onClick={() => navigate(`/projects/${projectId}/modules/${m.id}`)}
              className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-slate-100 dark:hover:bg-slate-900"
            >
              <div className="flex items-center gap-3">
                <Box size={16} className="text-slate-500" />
                <div>
                  <div className="text-sm">{m.name}</div>
                  <div className="text-xs text-slate-500">{m.path_prefix}</div>
                </div>
              </div>
              <div className="flex items-center gap-3">
                <span className="text-xs text-slate-500">bus factor {m.bus_factor ?? "—"}</span>
                <span className="text-sm font-medium">{m.risk_score ?? "—"}</span>
                <RiskBadge level={m.risk_level} />
              </div>
            </button>
          ))}
      </div>
    </div>
  );
}
