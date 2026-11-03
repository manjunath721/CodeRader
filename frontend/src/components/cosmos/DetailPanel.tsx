import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { X, FlaskConical, ChevronRight } from "lucide-react";
import { api } from "@/services/api";
import type {
  DeveloperDetail,
  LibraryEntry,
  ModuleDetail,
  ProjectFile,
  SimulationResult,
} from "@/types/api";

export interface CosmosSelection {
  kind: "developer" | "module" | "file" | "library";
  refId: string;
  nodeId: string;
  label: string;
}

interface Props {
  projectId: string;
  selection: CosmosSelection;
  fileEntry?: ProjectFile;
  libEntry?: LibraryEntry;
  filesExpanded?: boolean;
  onToggleFiles?: () => void;
  onClose: () => void;
}

function Insight({ children }: { children: React.ReactNode }) {
  return (
    <li className="flex gap-1.5 text-xs leading-relaxed text-slate-700 dark:text-slate-300">
      <ChevronRight size={13} className="mt-0.5 shrink-0 text-indigo-400" />
      <span>{children}</span>
    </li>
  );
}

function Bar({ value, color }: { value: number; color: string }) {
  return (
    <span className="h-1.5 w-16 shrink-0 overflow-hidden rounded-full bg-slate-200 dark:bg-slate-800">
      <span className="block h-full rounded-full" style={{ width: `${Math.min(100, value)}%`, background: color }} />
    </span>
  );
}

function DeveloperBody({ projectId, refId }: { projectId: string; refId: string }) {
  const [detail, setDetail] = useState<DeveloperDetail | null>(null);
  const [sim, setSim] = useState<SimulationResult | null>(null);
  const [simulating, setSimulating] = useState(false);
  useEffect(() => {
    setDetail(null);
    setSim(null);
    api.getDeveloper(refId).then(setDetail).catch(() => undefined);
  }, [refId]);

  async function simulate() {
    setSimulating(true);
    try {
      setSim(await api.simulateUnavailability(projectId, [refId]));
    } catch {
      // surfaced inline below via null state staying null
    } finally {
      setSimulating(false);
    }
  }

  if (!detail) return <div className="text-xs text-slate-500">Loading contributor profile…</div>;
  const top = [...detail.modules].sort((a, b) => b.score - a.score);
  return (
    <div className="space-y-4">
      <div className="grid grid-cols-2 gap-2">
        <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-2.5">
          <div className="text-[11px] text-slate-500">Modules touched</div>
          <div className="text-xl font-semibold tabular-nums">{top.length}</div>
        </div>
        <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-2.5">
          <div className="text-[11px] text-slate-500">Single-owner areas</div>
          <div className="text-xl font-semibold tabular-nums">{detail.single_owner_modules_count}</div>
        </div>
      </div>
      <div className="text-xs text-slate-400">
        Critical ownerships: <span className="text-slate-900 dark:text-slate-200">{detail.critical_ownership_count}</span> · Dependency
        exposure: <span className="text-slate-900 dark:text-slate-200">{detail.dependency_risk}</span>
      </div>
      <div>
        <div className="mb-1.5 text-xs font-medium text-slate-700 dark:text-slate-300">Knowledge coverage</div>
        <div className="space-y-1.5">
          {top.slice(0, 6).map((m) => (
            <div key={m.module_id} className="flex items-center justify-between gap-2 text-xs">
              <span className="truncate text-slate-700 dark:text-slate-300">{m.module_name}</span>
              <span className="flex items-center gap-1.5">
                <Bar value={m.score} color="#7dd3fc" />
                <span className="w-9 text-right tabular-nums text-slate-400">{Math.round(m.score)}</span>
              </span>
            </div>
          ))}
        </div>
      </div>
      <div>
        <div className="mb-1.5 text-xs font-medium text-slate-700 dark:text-slate-300">Derived insight</div>
        <ul className="space-y-1.5">
          {detail.single_owner_modules_count > 0 && (
            <Insight>
              Sole owner of {detail.single_owner_modules_count} module
              {detail.single_owner_modules_count === 1 ? "" : "s"} — a departure would leave knowledge gaps.
            </Insight>
          )}
          {detail.single_owner_modules_count === 0 && top.length > 1 && (
            <Insight>Knowledge is shared — no single-owner areas. Good resilience posture.</Insight>
          )}
          {detail.dependency_risk !== "LOW" && (
            <Insight>Works in modules with {detail.dependency_risk.toLowerCase()} downstream dependency exposure.</Insight>
          )}
        </ul>
      </div>
      <div className="rounded-lg border border-indigo-500/30 bg-indigo-500/5 p-3">
        <button
          onClick={simulate}
          disabled={simulating}
          className="inline-flex items-center gap-1.5 rounded-lg bg-indigo-500 px-3 py-1.5 text-xs font-medium text-white hover:bg-indigo-400 disabled:opacity-50"
        >
          <FlaskConical size={13} />
          {simulating ? "Simulating…" : sim ? "Re-run simulation" : "Simulate Knowledge Loss"}
        </button>
        {sim && (
          <div className="mt-2 text-xs text-slate-700 dark:text-slate-300">
            Resilience <span className="tabular-nums">{sim.resilience_before} → {sim.resilience_after}</span> ·{" "}
            <span className="tabular-nums">{sim.knowledge_impact_pct}%</span> knowledge at stake ·{" "}
            {sim.affected_modules.length} modules affected
            <div className="mt-1">
              <Link to={`/projects/${projectId}/simulation`} className="text-indigo-300 underline hover:text-indigo-200">
                Open in Simulation Lab
              </Link>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

function ModuleBody({
  refId,
  filesExpanded,
  onToggleFiles,
}: {
  refId: string;
  filesExpanded?: boolean;
  onToggleFiles?: () => void;
}) {
  const [detail, setDetail] = useState<ModuleDetail | null>(null);
  useEffect(() => {
    setDetail(null);
    api.getModule(refId).then(setDetail).catch(() => undefined);
  }, [refId]);
  if (!detail) return <div className="text-xs text-slate-500">Loading module intelligence…</div>;
  const levelColor =
    detail.risk_level === "CRITICAL" ? "#f87171" : detail.risk_level === "HIGH" ? "#fb923c" : detail.risk_level === "MODERATE" ? "#facc15" : "#4ade80";
  const top = [...detail.knowledge_distribution].sort((a, b) => b.score - a.score);
  return (
    <div className="space-y-4">
      <div className="flex items-center gap-3 rounded-lg border border-slate-200 dark:border-slate-800 p-3">
        <div className="text-3xl font-semibold tabular-nums" style={{ color: levelColor }}>
          {detail.risk_score ?? "—"}
        </div>
        <div className="text-xs text-slate-400">
          <div>Risk · {detail.risk_level ?? "unscored"}</div>
          <div className="mt-0.5">
            Bus factor {detail.bus_factor ?? "—"} · {detail.concentration_pct ?? "—"}% concentrated
          </div>
        </div>
      </div>
      <div className="grid grid-cols-3 gap-2 text-center">
        {[
          ["Docs", `${Math.round(detail.documentation_score * 100)}%`],
          ["Complexity", `${detail.complexity_avg.toFixed(1)}`],
          ["Churn 90d", `${detail.change_frequency_90d}`],
        ].map(([k, v]) => (
          <div key={k} className="rounded-lg border border-slate-200 dark:border-slate-800 p-2">
            <div className="text-[11px] text-slate-500">{k}</div>
            <div className="text-sm font-semibold tabular-nums">{v}</div>
          </div>
        ))}
      </div>
      <div>
        <div className="mb-1.5 text-xs font-medium text-slate-700 dark:text-slate-300">Top contributors</div>
        <div className="space-y-1.5">
          {top.slice(0, 5).map((c) => (
            <div key={c.developer_id} className="flex items-center justify-between gap-2 text-xs">
              <span className="truncate text-slate-700 dark:text-slate-300">{c.developer_name}</span>
              <span className="flex items-center gap-1.5">
                <Bar value={c.score} color={levelColor} />
                <span className="w-9 text-right tabular-nums text-slate-400">{Math.round(c.score)}</span>
              </span>
            </div>
          ))}
        </div>
      </div>
      {(detail.dependencies.length > 0 || detail.dependents.length > 0) && (
        <div className="text-xs">
          {detail.dependencies.length > 0 && (
            <div className="mb-1 text-slate-400">
              Depends on: <span className="text-orange-300">{detail.dependencies.join(", ")}</span>
            </div>
          )}
          {detail.dependents.length > 0 && (
            <div className="text-slate-400">
              Depended on by: <span className="text-orange-300">{detail.dependents.join(", ")}</span>
            </div>
          )}
        </div>
      )}
      {detail.backup_candidates.length > 0 && (
        <div>
          <div className="mb-1.5 text-xs font-medium text-slate-700 dark:text-slate-300">Backup candidates</div>
          <div className="space-y-1 text-xs text-slate-400">
            {detail.backup_candidates.slice(0, 3).map((b) => (
              <div key={b.developer_id} className="flex justify-between">
                <span>{b.developer_name}</span>
                <span className="tabular-nums">{b.compatibility}%</span>
              </div>
            ))}
          </div>
        </div>
      )}
      <div>
        <div className="mb-1.5 text-xs font-medium text-slate-700 dark:text-slate-300">Derived insight</div>
        <ul className="space-y-1.5">
          {(detail.bus_factor ?? 99) <= 1 && <Insight>Bus factor 1 — one departure away from a knowledge gap.</Insight>}
          {(detail.concentration_pct ?? 0) >= 70 && (detail.bus_factor ?? 99) > 1 && (
            <Insight>Knowledge is concentrated ({detail.concentration_pct}% HHI) — spread ownership.</Insight>
          )}
          {detail.documentation_score < 0.3 && <Insight>Documentation gap ({Math.round(detail.documentation_score * 100)}%) compounds the risk.</Insight>}
          {detail.is_critical_knowledge_area && <Insight>Flagged as a critical knowledge area for this project.</Insight>}
          {(detail.bus_factor ?? 99) > 2 && (detail.concentration_pct ?? 100) < 50 && detail.documentation_score >= 0.3 && (
            <Insight>Healthy spread with decent docs — a resilience anchor.</Insight>
          )}
        </ul>
      </div>
      {onToggleFiles && (
        <button
          onClick={onToggleFiles}
          className="w-full rounded-lg border border-slate-300 px-3 py-1.5 text-xs text-slate-700 hover:border-slate-500 dark:border-slate-700 dark:text-slate-300"
        >
          {filesExpanded ? "Collapse file layer" : "Expand file layer"}
        </button>
      )}
    </div>
  );
}

export default function DetailPanel({ projectId, selection, fileEntry, libEntry, filesExpanded, onToggleFiles, onClose }: Props) {
  const titles: Record<CosmosSelection["kind"], string> = {
    developer: "Contributor",
    module: "Module",
    file: "File",
    library: "Dependency",
  };
  return (
    <div className="pointer-events-auto absolute bottom-4 right-4 top-36 z-20 flex w-80 max-w-[calc(100%-2rem)] flex-col overflow-hidden rounded-xl border border-slate-200 bg-white shadow-2xl backdrop-blur dark:border-slate-700/60 dark:bg-slate-950/95">
      <div className="flex items-start justify-between gap-2 border-b border-slate-800 px-4 py-3">
        <div className="min-w-0">
          <div className="text-[11px] uppercase tracking-wider text-slate-500">{titles[selection.kind]}</div>
          <div className="truncate text-sm font-semibold text-slate-900 dark:text-slate-100">{selection.label}</div>
        </div>
        <button onClick={onClose} aria-label="Close details" className="rounded p-1 text-slate-500 hover:bg-slate-200 hover:text-slate-900 dark:hover:bg-slate-800 dark:hover:text-slate-200">
          <X size={15} />
        </button>
      </div>
      <div className="flex-1 overflow-y-auto px-4 py-3">
        {selection.kind === "developer" && <DeveloperBody projectId={projectId} refId={selection.refId} />}
        {selection.kind === "module" && (
          <ModuleBody refId={selection.refId} filesExpanded={filesExpanded} onToggleFiles={onToggleFiles} />
        )}
        {selection.kind === "file" && fileEntry && (
          <div className="space-y-3 text-xs">
            <div className="break-all font-mono text-[11px] text-slate-700 dark:text-slate-300">{fileEntry.path}</div>
            <div className="grid grid-cols-2 gap-2 text-center">
              {[
                ["Size", `${(fileEntry.size_bytes / 1024).toFixed(1)} KB`],
                ["Complexity", `${fileEntry.complexity}`],
                ["Doc coverage", `${fileEntry.doc_coverage_pct}%`],
                ["Language", fileEntry.language ?? "?"],
              ].map(([k, v]) => (
                <div key={k} className="rounded-lg border border-slate-200 dark:border-slate-800 p-2">
                  <div className="text-[11px] text-slate-500">{k}</div>
                  <div className="text-sm font-semibold tabular-nums">{v}</div>
                </div>
              ))}
            </div>
            {(fileEntry.is_test || fileEntry.is_config) && (
              <div className="text-slate-400">{[fileEntry.is_test && "test file", fileEntry.is_config && "config file"].filter(Boolean).join(" · ")}</div>
            )}
            <ul className="space-y-1.5">
              {fileEntry.complexity > 30 && fileEntry.doc_coverage_pct < 20 && (
                <Insight>Complex and under-documented — a quiet risk hotspot inside its module.</Insight>
              )}
              {!(fileEntry.complexity > 30 && fileEntry.doc_coverage_pct < 20) && (
                <Insight>Part of the {fileEntry.module_name ?? "unknown"} module — see the module view for ownership.</Insight>
              )}
            </ul>
          </div>
        )}
        {selection.kind === "library" && libEntry && (
          <div className="space-y-3 text-xs">
            <div className="grid grid-cols-2 gap-2 text-center">
              <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-2">
                <div className="text-[11px] text-slate-500">Imported in</div>
                <div className="text-sm font-semibold tabular-nums">{libEntry.file_count} files</div>
              </div>
              <div className="rounded-lg border border-slate-200 dark:border-slate-800 p-2">
                <div className="text-[11px] text-slate-500">Modules using it</div>
                <div className="text-sm font-semibold tabular-nums">{libEntry.used_by_modules.length}</div>
              </div>
            </div>
            <div className="text-slate-400">Used by: <span className="text-purple-300">{libEntry.used_by_modules.join(", ") || "—"}</span></div>
            <ul className="space-y-1.5">
              {libEntry.file_count >= 5 ? (
                <Insight>Deeply embedded ({libEntry.file_count} files) — upgrades need a blast-radius check.</Insight>
              ) : (
                <Insight>Lightly used third-party import, detected from real source imports.</Insight>
              )}
            </ul>
          </div>
        )}
      </div>
    </div>
  );
}
