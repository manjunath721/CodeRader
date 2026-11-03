import { useEffect, useMemo, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/services/api";
import type { DeveloperSummary, ModuleSummary, SimulationResult } from "@/types/api";
import { FlaskConical, GitBranch, X } from "lucide-react";

const LABEL_COLOR: Record<string, string> = {
  GOOD: "text-risk-low", MODERATE: "text-risk-moderate", AT_RISK: "text-risk-high", CRITICAL: "text-risk-critical",
};

function ImpactBar({ value }: { value: number }) {
  const pct = Math.round(value * 100);
  const color = pct >= 60 ? "bg-risk-critical" : pct >= 30 ? "bg-risk-high" : pct >= 10 ? "bg-risk-moderate" : "bg-risk-low";
  return (
    <span className="flex items-center gap-2 min-w-0">
      <span className="h-1.5 w-24 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
        <span className={`block h-full rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </span>
      <span className="text-xs tabular-nums text-slate-400 w-10 text-right">{pct}%</span>
    </span>
  );
}

export default function SimulationPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [devs, setDevs] = useState<DeveloperSummary[]>([]);
  const [modules, setModules] = useState<ModuleSummary[]>([]);
  const [selected, setSelected] = useState<string[]>([]);
  const [result, setResult] = useState<SimulationResult | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;
    api.listDevelopers(projectId).then(setDevs).catch((e) => setError(String(e)));
    api.listModules(projectId).then(setModules).catch(() => undefined);
  }, [projectId]);

  const nameById = useMemo(() => {
    const map = new Map<string, string>();
    for (const m of modules) map.set(m.id, m.name);
    for (const m of result?.affected_modules ?? []) map.set(m.id, m.name);
    return map;
  }, [modules, result]);

  const moduleName = (id: string) => nameById.get(id) ?? `${id.slice(0, 8)}…`;
  const selectedNames = devs.filter((d) => selected.includes(d.id)).map((d) => d.display_name);

  function toggle(id: string) {
    setSelected((prev) => (prev.includes(id) ? prev.filter((x) => x !== id) : [...prev, id]));
  }

  async function run() {
    if (!projectId || selected.length === 0) return;
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      setResult(await api.simulateUnavailability(projectId, selected));
    } catch (err) {
      setError(String(err));
    } finally {
      setRunning(false);
    }
  }

  const propagationRoots = useMemo(() => {
    if (!result) return [];
    return Object.entries(result.risk_propagation)
      .map(([rootId, impacts]) => ({
        rootId,
        impacts: Object.entries(impacts).sort((a, b) => b[1] - a[1]),
      }))
      .sort((a, b) => (b.impacts[0]?.[1] ?? 0) - (a.impacts[0]?.[1] ?? 0));
  }, [result]);

  return (
    <div className="space-y-6">
      <h1 className="text-xl font-semibold">Simulation</h1>
      <p className="text-sm text-slate-400 -mt-4">
        Repository-derived potential-impact estimate — not a prediction of actual production incidents or a
        personnel decision.
      </p>

      <div className="rounded-xl border border-slate-200 bg-white p-5 space-y-4 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none">
        <div className="text-sm font-medium text-slate-700 dark:text-slate-300">Select developer(s) to simulate as unavailable</div>
        <div className="flex flex-wrap gap-2">
          {devs.map((d) => (
            <button
              key={d.id}
              onClick={() => toggle(d.id)}
              className={`rounded-full border px-3 py-1.5 text-sm transition-colors ${
                selected.includes(d.id)
                  ? "border-slate-900 bg-slate-900 text-white dark:border-white dark:bg-white dark:text-slate-900"
                  : "border-slate-300 text-slate-600 hover:border-slate-500 dark:border-slate-700 dark:text-slate-300"
              }`}
            >
              {d.display_name}
            </button>
          ))}
          {devs.length === 0 && <div className="text-sm text-slate-500">No developers yet — run analysis first.</div>}
        </div>
        {selectedNames.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5 text-xs text-slate-400">
            <span>Simulating absence of:</span>
            {selectedNames.map((n) => (
              <span key={n} className="inline-flex items-center gap-1 rounded-full bg-slate-200 px-2 py-0.5 text-slate-700 dark:bg-slate-800 dark:text-slate-200">
                {n}
                <button
                  aria-label={`Remove ${n}`}
                  onClick={() => setSelected((prev) => prev.filter((id) => devs.find((d) => d.id === id)?.display_name !== n))}
                  className="hover:text-white"
                >
                  <X size={12} />
                </button>
              </span>
            ))}
          </div>
        )}
        <button
          onClick={run}
          disabled={selected.length === 0 || running}
          className="inline-flex items-center gap-2 rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
        >
          <FlaskConical size={16} />
          {running ? "Running…" : `Run simulation${selected.length > 1 ? ` (${selected.length} developers)` : ""}`}
        </button>
        {error && <div className="text-sm text-risk-critical">{error}</div>}
      </div>

      {result && (
        <div className="space-y-6">
          <div className="grid grid-cols-1 sm:grid-cols-3 gap-4">
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none">
              <div className="text-xs text-slate-500 mb-1">Resilience</div>
              <div className="text-2xl font-semibold tabular-nums">
                <span className="text-slate-400">{result.resilience_before}</span>
                {" → "}
                <span className={LABEL_COLOR[result.resilience_label_after] ?? ""}>{result.resilience_after}</span>
              </div>
              <div className="text-xs text-slate-500 mt-1">
                {result.resilience_label_before} → {result.resilience_label_after}
              </div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none">
              <div className="text-xs text-slate-500 mb-1">Knowledge potentially affected</div>
              <div className="text-2xl font-semibold tabular-nums">{result.knowledge_impact_pct}%</div>
            </div>
            <div className="rounded-xl border border-slate-200 bg-white p-4 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none">
              <div className="text-xs text-slate-500 mb-1">Affected modules</div>
              <div className="text-2xl font-semibold tabular-nums">{result.affected_modules.length}</div>
            </div>
          </div>

          {propagationRoots.length > 0 && (
            <div>
              <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-1 flex items-center gap-1.5">
                <GitBranch size={14} className="text-slate-500" /> Risk propagation tree
              </div>
              <p className="text-xs text-slate-500 mb-2">
                Impact radiates from each directly-affected module to its dependents (decay 0.6 per hop).
              </p>
              <div className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-200 shadow-sm dark:border-slate-800 dark:bg-transparent dark:divide-slate-800 dark:shadow-none">
                {propagationRoots.map(({ rootId, impacts }) => (
                  <div key={rootId} className="px-4 py-3">
                    <div className="text-sm font-medium text-slate-200 mb-2">
                      {moduleName(rootId)}
                      <span className="ml-2 text-xs font-normal text-slate-500">impact source</span>
                    </div>
                    <div className="ml-3 space-y-1.5 border-l border-slate-200 pl-3 dark:border-slate-800">
                      {impacts.map(([targetId, impact]) => (
                        <div key={targetId} className="flex items-center justify-between gap-3 text-sm">
                          <span className={targetId === rootId ? "text-slate-200" : "text-slate-400"}>
                            {targetId === rootId ? "└ self (direct knowledge loss)" : `└ ${moduleName(targetId)}`}
                          </span>
                          <ImpactBar value={impact} />
                        </div>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          <div>
            <div className="text-sm font-medium text-slate-700 dark:text-slate-300 mb-2">Affected modules &amp; backup candidates</div>
            <div className="rounded-xl border border-slate-200 bg-white divide-y divide-slate-200 shadow-sm dark:border-slate-800 dark:bg-transparent dark:divide-slate-800 dark:shadow-none">
              {result.affected_modules.map((m) => (
                <div key={m.id} className="px-4 py-3">
                  <div className="text-sm font-medium mb-1">{m.name}</div>
                  {(result.backup_candidates[m.name] ?? []).slice(0, 3).map((c) => (
                    <div key={c.developer_id} className="text-xs text-slate-400 flex justify-between py-0.5">
                      <span>{c.developer_name}</span>
                      <span className="tabular-nums">{c.compatibility}% compatibility</span>
                    </div>
                  ))}
                  {(result.backup_candidates[m.name] ?? []).length === 0 && (
                    <div className="text-xs text-slate-500">No backup candidates identified.</div>
                  )}
                </div>
              ))}
              {result.affected_modules.length === 0 && (
                <div className="px-4 py-3 text-sm text-slate-500">No modules affected by this scenario.</div>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
