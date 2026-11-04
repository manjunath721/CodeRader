import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/services/api";
import type { AnalysisComparison, AnalysisRun } from "@/types/api";
import { ArrowRight, CheckCircle2, Clock, Download, GitCommit, GitCompare, History, XCircle } from "lucide-react";

export default function HistoryPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [runs, setRuns] = useState<AnalysisRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [baseRunId, setBaseRunId] = useState<string>("");
  const [targetRunId, setTargetRunId] = useState<string>("");
  const [comparison, setComparison] = useState<AnalysisComparison | null>(null);
  const [comparing, setComparing] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    async function loadRuns() {
      try {
        const data = await api.listAnalysisRuns(projectId!);
        setRuns(data);
        if (data.length >= 2) {
          setBaseRunId(data[1].id);
          setTargetRunId(data[0].id);
        } else if (data.length === 1) {
          setTargetRunId(data[0].id);
        }
      } catch (err) {
        console.error(err);
      } finally {
        setLoading(false);
      }
    }
    loadRuns();
  }, [projectId]);

  const handleCompare = async () => {
    if (!projectId || !baseRunId || !targetRunId || baseRunId === targetRunId) return;
    setComparing(true);
    try {
      const comp = await api.compareRuns(projectId, baseRunId, targetRunId);
      setComparison(comp);
    } catch (err) {
      console.error(err);
    } finally {
      setComparing(false);
    }
  };

  const handleExport = (runId: string, format: "json" | "csv") => {
    if (!projectId) return;
    window.open(`/api/projects/${projectId}/analysis-runs/${runId}/export?format=${format}`, "_blank");
  };

  if (loading) {
    return <div className="text-sm text-slate-500">Loading analysis history…</div>;
  }

  return (
    <div className="space-y-8 max-w-5xl">
      <div>
        <h1 className="text-2xl font-bold tracking-tight">Analysis History &amp; Comparison</h1>
        <p className="text-sm text-slate-500">
          Track immutable historical snapshots across Git commits, compare metrics, and audit risk shifts.
        </p>
      </div>

      {/* Comparison Selector */}
      {runs.length >= 2 && (
        <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-slate-900 space-y-4">
          <div className="flex items-center gap-2 text-sm font-semibold">
            <GitCompare size={18} />
            <span>Compare Snapshots</span>
          </div>

          <div className="flex flex-wrap items-center gap-3">
            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs text-slate-500 mb-1">Baseline Run</label>
              <select
                value={baseRunId}
                onChange={(e) => setBaseRunId(e.target.value)}
                className="w-full rounded-lg border border-slate-300 p-2 text-xs bg-transparent dark:border-slate-700"
              >
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.scan_mode.toUpperCase()} ({r.rescan_type || "manual"}) — {r.completed_at ? new Date(r.completed_at).toLocaleString() : r.id.slice(0, 8)}
                  </option>
                ))}
              </select>
            </div>

            <ArrowRight size={18} className="text-slate-400 mt-4" />

            <div className="flex-1 min-w-[200px]">
              <label className="block text-xs text-slate-500 mb-1">Comparison Run</label>
              <select
                value={targetRunId}
                onChange={(e) => setTargetRunId(e.target.value)}
                className="w-full rounded-lg border border-slate-300 p-2 text-xs bg-transparent dark:border-slate-700"
              >
                {runs.map((r) => (
                  <option key={r.id} value={r.id}>
                    {r.scan_mode.toUpperCase()} ({r.rescan_type || "manual"}) — {r.completed_at ? new Date(r.completed_at).toLocaleString() : r.id.slice(0, 8)}
                  </option>
                ))}
              </select>
            </div>

            <button
              onClick={handleCompare}
              disabled={comparing || baseRunId === targetRunId}
              className="mt-4 rounded-lg bg-slate-900 text-white px-4 py-2 text-xs font-medium hover:bg-slate-800 disabled:opacity-50 dark:bg-white dark:text-slate-900"
            >
              {comparing ? "Comparing…" : "Diff Runs"}
            </button>
          </div>

          {comparison && (
            <div className="mt-4 pt-4 border-t border-slate-100 dark:border-slate-800 space-y-4">
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-950">
                  <div className="text-xs text-slate-500">Resilience Shift</div>
                  <div className="text-lg font-bold">
                    {comparison.resilience_before ?? "—"} → {comparison.resilience_after ?? "—"}
                    <span
                      className={`ml-2 text-xs font-semibold ${
                        comparison.resilience_delta >= 0 ? "text-emerald-600" : "text-rose-600"
                      }`}
                    >
                      {comparison.resilience_delta > 0 ? `+${comparison.resilience_delta}` : comparison.resilience_delta}
                    </span>
                  </div>
                </div>

                <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-950">
                  <div className="text-xs text-slate-500">Newly Introduced High Risks</div>
                  <div className="text-lg font-bold text-rose-600">
                    {comparison.newly_introduced_risks.length}
                  </div>
                </div>

                <div className="rounded-lg bg-slate-50 p-3 dark:bg-slate-950">
                  <div className="text-xs text-slate-500">Resolved Risks</div>
                  <div className="text-lg font-bold text-emerald-600">
                    {comparison.resolved_risks.length}
                  </div>
                </div>
              </div>

              {comparison.risk_changes.length > 0 && (
                <div>
                  <div className="text-xs font-semibold text-slate-700 dark:text-slate-300 mb-2">
                    Module Risk Changes
                  </div>
                  <div className="divide-y divide-slate-100 dark:divide-slate-800 text-xs">
                    {comparison.risk_changes.slice(0, 8).map((rc) => (
                      <div key={rc.module_id} className="py-2 flex items-center justify-between">
                        <span className="font-mono text-slate-800 dark:text-slate-200">{rc.name}</span>
                        <div className="flex items-center gap-3">
                          <span className="text-slate-500">{rc.old_score ?? "—"} → {rc.new_score ?? "—"}</span>
                          <span
                            className={`font-medium ${
                              rc.delta > 0 ? "text-rose-600" : rc.delta < 0 ? "text-emerald-600" : "text-slate-400"
                            }`}
                          >
                            {rc.delta > 0 ? `+${rc.delta}` : rc.delta}
                          </span>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          )}
        </div>
      )}

      {/* Runs Table */}
      <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm dark:border-slate-800 dark:bg-slate-900">
        <div className="p-4 border-b border-slate-200 dark:border-slate-800 flex items-center gap-2">
          <History size={16} />
          <h2 className="text-sm font-semibold">Historical Analysis Runs</h2>
        </div>

        <div className="divide-y divide-slate-100 dark:divide-slate-800">
          {runs.map((r) => (
            <div key={r.id} className="p-4 flex flex-wrap items-center justify-between gap-4">
              <div className="space-y-1">
                <div className="flex items-center gap-2">
                  {r.status === "complete" ? (
                    <CheckCircle2 size={16} className="text-emerald-500" />
                  ) : r.status === "failed" ? (
                    <XCircle size={16} className="text-rose-500" />
                  ) : (
                    <Clock size={16} className="text-amber-500" />
                  )}
                  <span className="font-semibold text-sm capitalize">{r.status}</span>
                  <span className="rounded bg-slate-100 px-2 py-0.5 text-xs text-slate-700 dark:bg-slate-800 dark:text-slate-300">
                    {r.scan_mode}
                  </span>
                  {r.rescan_type && (
                    <span className="rounded bg-indigo-50 px-2 py-0.5 text-xs text-indigo-700 dark:bg-indigo-950/60 dark:text-indigo-300">
                      {r.rescan_type}
                    </span>
                  )}
                </div>
                <div className="flex items-center gap-3 text-xs text-slate-500">
                  {r.commit_sha && (
                    <span className="flex items-center gap-1 font-mono">
                      <GitCommit size={12} />
                      {r.commit_sha.slice(0, 7)}
                    </span>
                  )}
                  <span>
                    {r.completed_at
                      ? new Date(r.completed_at).toLocaleString()
                      : r.started_at
                      ? `Started ${new Date(r.started_at).toLocaleTimeString()}`
                      : "Pending"}
                  </span>
                </div>
              </div>

              {r.status === "complete" && (
                <div className="flex items-center gap-2">
                  <button
                    onClick={() => handleExport(r.id, "json")}
                    className="flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                  >
                    <Download size={12} />
                    <span>JSON</span>
                  </button>
                  <button
                    onClick={() => handleExport(r.id, "csv")}
                    className="flex items-center gap-1 rounded-lg border border-slate-200 px-2.5 py-1 text-xs text-slate-600 hover:bg-slate-50 dark:border-slate-700 dark:text-slate-300 dark:hover:bg-slate-800"
                  >
                    <Download size={12} />
                    <span>CSV</span>
                  </button>
                </div>
              )}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}
