import { useCallback, useEffect, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import { api } from "@/services/api";
import type { AnalysisRun, DashboardData } from "@/types/api";
import RiskBadge from "@/components/RiskBadge";
import { CheckCircle2, CircleDashed, PlayCircle, RefreshCw, XCircle, Trash2 } from "lucide-react";

const STAGE_LABELS: Record<string, string> = {
  repository_ingestion: "Repository ingestion",
  commit_analysis: "Commit analysis",
  knowledge_scoring: "Knowledge scoring",
  graph_construction: "Graph construction",
  risk_calculation: "Risk calculation",
  recommendations: "Recommendations",
};
const STAGE_ORDER = Object.keys(STAGE_LABELS);

const LABEL_COLOR: Record<string, string> = {
  GOOD: "text-risk-low",
  MODERATE: "text-risk-moderate",
  AT_RISK: "text-risk-high",
  CRITICAL: "text-risk-critical",
};

export default function DashboardPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [data, setData] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [scanMode, setScanMode] = useState<"quick" | "full">("full");
  const [activeRun, setActiveRun] = useState<AnalysisRun | null>(null);
  const cancelledRef = useRef(false);
  const navigate = useNavigate();

  const load = useCallback(() => {
    if (!projectId) return;
    api.getDashboard(projectId).then(setData).catch((e) => setError(String(e)));
  }, [projectId]);

  useEffect(load, [load]);

  async function handleAnalyze() {
    if (!projectId) return;
    setAnalyzing(true);
    setError(null);
    cancelledRef.current = false;
    try {
      const run = await api.startAnalysis(projectId, scanMode);
      setActiveRun(run);
      let current = run;
      while (current.status === "pending" || current.status === "running") {
        await new Promise((r) => setTimeout(r, 1200));
        current = await api.getAnalysisRun(projectId, run.id);
        setActiveRun(current);
      }
      if (current.status === "failed") {
        setError(current.error_message ?? "Analysis failed.");
      }
      load();
    } catch (err) {
      setError(String(err));
    } finally {
      setAnalyzing(false);
    }
  }

  async function handleCancel() {
    if (!projectId || !activeRun) return;
    cancelledRef.current = true;
    await api.cancelAnalysisRun(projectId, activeRun.id);
  }

  async function handleDelete() {
    if (!projectId || !data) return;
    if (!window.confirm(`Delete project "${data.project_name}" and all of its analysis data? This cannot be undone.`)) return;
    try {
      await api.deleteProject(projectId);
      navigate("/");
    } catch (err) {
      setError(String(err));
    }
  }

  if (error) return <div className="text-risk-critical text-sm">{error}</div>;
  if (!data) return <div className="text-slate-500 text-sm">Loading…</div>;

  const total = Object.values(data.risk_distribution).reduce((a, b) => a + b, 0);

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-xl font-semibold">{data.project_name}</h1>
          {data.is_demo && <div className="text-xs text-slate-500">Demo data (synthetic)</div>}
        </div>
        <div className="flex items-center gap-2">
          {!analyzing && (
            <select
              value={scanMode}
              onChange={(e) => setScanMode(e.target.value as "quick" | "full")}
              className="rounded-lg bg-slate-100 border border-slate-200 px-2 py-2 text-xs dark:bg-slate-900 dark:border-slate-800"
              title="Quick Scan: bounded-depth, fast first look. Full Historical Scan: complete history."
            >
              <option value="full">Full Historical Scan</option>
              <option value="quick">Quick Scan</option>
            </select>
          )}
          {analyzing ? (
            <button
              onClick={handleCancel}
              disabled={cancelledRef.current}
              className="inline-flex items-center gap-2 rounded-lg border border-slate-300 px-4 py-2 text-sm font-medium text-slate-600 hover:border-risk-critical hover:text-risk-critical disabled:opacity-50 dark:border-slate-700 dark:text-slate-300"
            >
              <XCircle size={16} />
              {cancelledRef.current ? "Cancelling…" : "Cancel"}
            </button>
          ) : null}
          <button
            onClick={handleAnalyze}
            disabled={analyzing}
            className="inline-flex items-center gap-2 rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
          >
            {analyzing ? <RefreshCw size={16} className="animate-spin" /> : <PlayCircle size={16} />}
            {analyzing ? "Analyzing…" : data.last_analysis_run_id ? "Re-run analysis" : "Run analysis"}
          </button>
          {!analyzing && (
            <button
              onClick={handleDelete}
              title="Delete project"
              aria-label="Delete project"
              className="rounded-lg border border-slate-200 p-2 text-slate-500 hover:border-risk-critical hover:text-risk-critical dark:border-slate-800"
            >
              <Trash2 size={16} />
            </button>
          )}
        </div>
      </div>

      {analyzing && activeRun && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-3 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none">
          <div className="text-sm font-medium text-slate-700 dark:text-slate-300">
            {activeRun.status === "pending" ? "Starting…" : "Running analysis"}
            {activeRun.scan_mode === "quick" && <span className="text-slate-500"> (Quick Scan)</span>}
          </div>
          <div className="space-y-1.5">
            {STAGE_ORDER.map((stage) => {
              const stageStatus = activeRun.stage_status[stage];
              return (
                <div key={stage} className="flex items-center gap-2 text-xs">
                  {stageStatus === "complete" ? (
                    <CheckCircle2 size={14} className="text-risk-low" />
                  ) : (
                    <CircleDashed size={14} className="text-slate-600" />
                  )}
                  <span className={stageStatus === "complete" ? "text-slate-700 dark:text-slate-300" : "text-slate-400 dark:text-slate-600"}>
                    {STAGE_LABELS[stage]}
                  </span>
                </div>
              );
            })}
          </div>
          {activeRun.progress?.ingestion &&
            Object.values(activeRun.progress.ingestion).map((p, i) => (
              <div key={i} className="text-xs text-slate-500 border-t border-slate-200 pt-2 dark:border-slate-800">
                {p.incremental ? "Incremental scan — " : "Full scan — "}
                {p.commits_inserted} new commit{p.commits_inserted === 1 ? "" : "s"} ingested
                {p.commits_already_present > 0 && ` (${p.commits_already_present} already indexed)`},{" "}
                {p.files_analyzed} file{p.files_analyzed === 1 ? "" : "s"} analyzed
                {p.files_cached > 0 && `, ${p.files_cached} served from cache`}
                {p.files_skipped_unreadable > 0 && `, ${p.files_skipped_unreadable} skipped (unreadable)`}.
              </div>
            ))}
        </div>
      )}

      {!data.last_analysis_run_id && !analyzing && (
        <div className="rounded-lg border border-slate-200 bg-white p-6 text-sm text-slate-600 shadow-sm dark:border-slate-800 dark:bg-transparent dark:text-slate-400 dark:shadow-none">
          This project hasn't been analyzed yet. Click "Run analysis" to ingest the repository and compute
          knowledge, risk, and resilience metrics.
        </div>
      )}

      {data.last_analysis_run_id && (
        <>
          <div className="grid grid-cols-3 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none">
              <div className="text-xs text-slate-500 mb-1">Project Resilience</div>
              <div className={`text-4xl font-semibold ${LABEL_COLOR[data.resilience_label ?? ""] ?? ""}`}>
                {data.resilience_score ?? "—"}
                <span className="text-lg text-slate-500">/100</span>
              </div>
              <div className="text-xs text-slate-500 mt-1">{data.resilience_label}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none">
              <div className="text-xs text-slate-500 mb-1">Developers</div>
              <div className="text-4xl font-semibold">{data.developer_count}</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none">
              <div className="text-xs text-slate-500 mb-1">Modules</div>
              <div className="text-4xl font-semibold">{data.module_count}</div>
            </div>
          </div>

          <div>
            <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Risk distribution</div>
            <div className="flex h-3 w-full overflow-hidden rounded-full bg-slate-200 dark:bg-slate-900">
              {(["LOW", "MODERATE", "HIGH", "CRITICAL"] as const).map((level) => {
                const pct = total ? (data.risk_distribution[level] / total) * 100 : 0;
                const colorClass = {
                  LOW: "bg-risk-low", MODERATE: "bg-risk-moderate", HIGH: "bg-risk-high", CRITICAL: "bg-risk-critical",
                }[level];
                return pct ? <div key={level} className={colorClass} style={{ width: `${pct}%` }} /> : null;
              })}
            </div>
            <div className="flex gap-4 mt-2 text-xs text-slate-500">
              {(["LOW", "MODERATE", "HIGH", "CRITICAL"] as const).map((level) => (
                <span key={level}>
                  {level}: {data.risk_distribution[level]}
                </span>
              ))}
            </div>
          </div>

          <div>
            <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Top risk modules</div>
            <div className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-200 shadow-sm dark:border-slate-800 dark:bg-transparent dark:divide-slate-800 dark:shadow-none">
              {data.top_risk_modules.map((m) => (
                <button
                  key={m.id}
                  onClick={() => navigate(`/projects/${projectId}/modules/${m.id}`)}
                  className="w-full flex items-center justify-between px-4 py-3 text-left hover:bg-slate-100 dark:hover:bg-slate-900"
                >
                  <span className="text-sm">{m.name}</span>
                  <div className="flex items-center gap-3">
                    <span className="text-xs text-slate-500">bus factor {m.bus_factor}</span>
                    <span className="text-sm font-medium">{m.risk_score}</span>
                    <RiskBadge level={m.risk_level} />
                  </div>
                </button>
              ))}
              {data.top_risk_modules.length === 0 && (
                <div className="px-4 py-3 text-sm text-slate-500">No modules detected.</div>
              )}
            </div>
          </div>

          {data.critical_knowledge_areas.length > 0 && (
            <div>
              <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Critical knowledge areas</div>
              <div className="flex flex-wrap gap-2">
                {data.critical_knowledge_areas.map((m) => (
                  <button
                    key={m.id}
                    onClick={() => navigate(`/projects/${projectId}/modules/${m.id}`)}
                    className="rounded-full border border-risk-critical/40 bg-risk-critical/10 text-risk-critical px-3 py-1 text-xs"
                  >
                    {m.name}
                  </button>
                ))}
              </div>
            </div>
          )}
        </>
      )}
    </div>
  );
}
