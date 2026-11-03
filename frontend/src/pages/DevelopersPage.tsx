import { useEffect, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/services/api";
import type { DeveloperSummary } from "@/types/api";
import { UserRound } from "lucide-react";

export default function DevelopersPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [devs, setDevs] = useState<DeveloperSummary[] | null>(null);
  const navigate = useNavigate();

  useEffect(() => {
    if (projectId) api.listDevelopers(projectId).then(setDevs);
  }, [projectId]);

  return (
    <div className="space-y-4">
      <h1 className="text-xl font-semibold">Developers</h1>
      {devs === null && <div className="text-slate-500 text-sm">Loading…</div>}
      {devs?.length === 0 && (
        <div className="text-slate-500 text-sm">No developers yet — run analysis from the Dashboard.</div>
      )}
      <div className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-200 shadow-sm dark:border-slate-800 dark:bg-transparent dark:divide-slate-800 dark:shadow-none">
        {devs?.map((d) => (
          <button
            key={d.id}
            onClick={() => navigate(`/projects/${projectId}/developers/${d.id}`)}
            className="w-full flex items-center gap-3 px-4 py-3 text-left hover:bg-slate-100 dark:hover:bg-slate-900"
          >
            <UserRound size={16} className="text-slate-500" />
            <div>
              <div className="text-sm">{d.display_name}</div>
              {d.primary_email && <div className="text-xs text-slate-500">{d.primary_email}</div>}
            </div>
          </button>
        ))}
      </div>
    </div>
  );
}
