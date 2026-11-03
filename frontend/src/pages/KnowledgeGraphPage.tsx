import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams } from "react-router-dom";
import ReactFlow, {
  Background,
  BackgroundVariant,
  Controls,
  MiniMap,
  Panel,
  type Node,
  type ReactFlowInstance,
} from "reactflow";
import "reactflow/dist/style.css";
import { Maximize2, Search } from "lucide-react";
import { api } from "@/services/api";
import { useTheme } from "@/theme";
import type {
  DashboardData,
  KnowledgeGraphData,
  LibraryEntry,
  ModuleSummary,
  ProjectFile,
} from "@/types/api";
import { buildCosmos, RISK_COLOR, type CosmosMode, type CosmosNodeData } from "@/components/cosmos/cosmosLayout";
import { cosmosNodeTypes } from "@/components/cosmos/CosmosNodes";
import DetailPanel, { type CosmosSelection } from "@/components/cosmos/DetailPanel";

const MODES: { id: CosmosMode; label: string; hint: string }[] = [
  { id: "knowledge", label: "Knowledge", hint: "Who knows what — contributors orbit the modules they own" },
  { id: "dependencies", label: "Dependencies", hint: "How modules depend on each other and on third-party libraries" },
  { id: "ownership", label: "Ownership", hint: "Bus-factor view — red modules hinge on a single person" },
  { id: "contributions", label: "Contributions", hint: "Activity view — node size follows breadth of contribution" },
  { id: "risk", label: "Risk", hint: "Risk view — glow and pulse follow the measured risk level" },
];

export default function KnowledgeGraphPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const { theme } = useTheme();
  const light = theme === "light";
  const [graph, setGraph] = useState<KnowledgeGraphData | null>(null);
  const [moduleInfo, setModuleInfo] = useState<ModuleSummary[]>([]);
  const [files, setFiles] = useState<ProjectFile[]>([]);
  const [libraries, setLibraries] = useState<LibraryEntry[]>([]);
  const [dashboard, setDashboard] = useState<DashboardData | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [mode, setMode] = useState<CosmosMode>("knowledge");
  const [showFiles, setShowFiles] = useState(false);
  const [showLibraries, setShowLibraries] = useState(true);
  const [expandedModules, setExpandedModules] = useState<Set<string>>(new Set());
  const [selection, setSelection] = useState<CosmosSelection | null>(null);
  const [query, setQuery] = useState("");
  const flowRef = useRef<ReactFlowInstance | null>(null);

  useEffect(() => {
    if (!projectId) return;
    setError(null);
    setGraph(null);
    api.getKnowledgeGraph(projectId).then(setGraph).catch((e) => setError(String(e)));
    api.listModules(projectId).then(setModuleInfo).catch(() => undefined);
    api.listFiles(projectId).then((f) => {
      setFiles(f);
      setShowFiles(f.length > 0 && f.length <= 40);
    }).catch(() => undefined);
    api.listLibraries(projectId).then(setLibraries).catch(() => undefined);
    api.getDashboard(projectId).then(setDashboard).catch(() => undefined);
  }, [projectId]);

  const riskByNodeId = useMemo(() => {
    const map = new Map<string, ModuleSummary>();
    for (const m of moduleInfo) map.set(`mod:${m.id}`, m);
    return map;
  }, [moduleInfo]);

  const moduleNodeByName = useMemo(() => {
    const map = new Map<string, string>();
    for (const m of moduleInfo) map.set(m.name, `mod:${m.id}`);
    return map;
  }, [moduleInfo]);

  const fileById = useMemo(() => new Map(files.map((f) => [f.id, f])), [files]);
  const libByName = useMemo(() => new Map(libraries.map((l) => [l.name, l])), [libraries]);

  const { nodes, edges } = useMemo(
    () =>
      graph
        ? buildCosmos({
            graph,
            riskByNodeId,
            files,
            libraries,
            moduleNodeByName,
            mode,
            showFiles,
            showLibraries,
            expandedModules,
            selectedId: selection?.nodeId ?? null,
            light,
          })
        : { nodes: [], edges: [] as never[] },
    [graph, riskByNodeId, files, libraries, moduleNodeByName, mode, showFiles, showLibraries, expandedModules, selection, light],
  );

  // Selection may point at a node hidden by the new mode — clear it.
  useEffect(() => {
    if (selection && !nodes.some((n) => n.id === selection.nodeId)) setSelection(null);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [mode, showFiles, showLibraries]);

  const entityCount = nodes.filter((n) => n.data.kind !== "cluster").length;
  const gaps = moduleInfo.filter((m) => (m.bus_factor ?? 99) <= 1).length;

  const focusNode = useCallback(
    (node: Node<CosmosNodeData>) => {
      const inst = flowRef.current;
      if (!inst) return;
      const w = (node.style?.width as number) ?? node.data.size ?? 60;
      const h = (node.style?.height as number) ?? node.data.size ?? 60;
      inst.setCenter(node.position.x + w / 2, node.position.y + h / 2, { zoom: 1.1, duration: 600 });
    },
    [],
  );

  function handleNodeClick(_: unknown, node: Node<CosmosNodeData>) {
    const d = node.data;
    if (d.kind === "cluster") return;
    focusNode(node);
    if (d.kind === "developer") setSelection({ kind: "developer", refId: d.refId ?? "", nodeId: node.id, label: d.label });
    else if (d.kind === "module") setSelection({ kind: "module", refId: d.refId ?? "", nodeId: node.id, label: d.label });
    else if (d.kind === "file") setSelection({ kind: "file", refId: d.refId ?? "", nodeId: node.id, label: d.label });
    else if (d.kind === "library") setSelection({ kind: "library", refId: d.refId ?? "", nodeId: node.id, label: d.label });
  }

  function handleNodeDoubleClick(_: unknown, node: Node<CosmosNodeData>) {
    if (node.data.kind !== "module" || !showFiles || !node.data.expandable) return;
    setExpandedModules((prev) => {
      const next = new Set(prev);
      if (next.has(node.id)) next.delete(node.id);
      else next.add(node.id);
      return next;
    });
  }

  function handleSearch(e: React.FormEvent) {
    e.preventDefault();
    const q = query.trim().toLowerCase();
    if (!q) return;
    const hit =
      nodes.find((n) => n.data.kind !== "cluster" && n.data.label.toLowerCase() === q) ??
      nodes.find((n) => n.data.kind !== "cluster" && n.data.label.toLowerCase().includes(q));
    if (hit) handleNodeClick(null, hit);
  }

  const stats: [string, string][] = [
    ["Entities", `${entityCount}`],
    ["Relationships", `${edges.length}`],
    ["Knowledge gaps", `${gaps} modules`],
    ["Resilience", dashboard?.resilience_score != null ? `${dashboard.resilience_score} · ${dashboard.resilience_label}` : "—"],
  ];

  return (
    <div className="space-y-3 h-full flex flex-col">
      <div>
        <h1 className="text-xl font-semibold">
          Knowledge Cosmos{" "}
          <span className="text-xs font-normal text-slate-500">software intelligence map</span>
        </h1>
        <p className="text-xs text-slate-500 mt-0.5">{MODES.find((m) => m.id === mode)?.hint}</p>
      </div>

      <div className="grid grid-cols-2 sm:grid-cols-4 gap-2">
        {stats.map(([k, v]) => (
          <div key={k} className="rounded-xl border border-slate-200 bg-white px-3 py-2 shadow-sm dark:border-slate-800 dark:bg-slate-950/60 dark:shadow-none">
            <div className="text-[11px] text-slate-500">{k}</div>
            <div className="text-sm font-semibold tabular-nums text-slate-900 dark:text-slate-100">{v}</div>
          </div>
        ))}
      </div>

      <div className="flex flex-wrap items-center gap-2">
        <div className="flex rounded-lg border border-slate-200 overflow-hidden dark:border-slate-800">
          {MODES.map((m) => (
            <button
              key={m.id}
              onClick={() => setMode(m.id)}
              className={`px-3 py-1.5 text-xs font-medium transition-colors ${
                mode === m.id
                  ? "bg-indigo-500 text-white"
                  : "text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-200"
              }`}
            >
              {m.label}
            </button>
          ))}
        </div>
        {files.length > 0 && (
          <button
            onClick={() => setShowFiles((v) => !v)}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              showFiles
                ? "border-slate-900 bg-slate-900 text-white dark:border-slate-400 dark:bg-slate-200 dark:text-slate-900"
                : "border-slate-300 text-slate-500 dark:border-slate-700 dark:text-slate-400"
            }`}
          >
            Files{showFiles ? ` (${files.length})` : ""}
          </button>
        )}
        {libraries.length > 0 && (
          <button
            onClick={() => setShowLibraries((v) => !v)}
            className={`rounded-full border px-3 py-1 text-xs transition-colors ${
              showLibraries
                ? "border-purple-500 bg-purple-500/15 text-purple-700 dark:border-purple-400 dark:text-purple-200"
                : "border-slate-300 text-slate-500 dark:border-slate-700 dark:text-slate-400"
            }`}
          >
            Libraries{showLibraries ? ` (${libraries.length})` : ""}
          </button>
        )}
        <form onSubmit={handleSearch} className="flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-2 py-1 dark:border-slate-800 dark:bg-slate-900">
          <Search size={13} className="text-slate-500" />
          <input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder="Find node…"
            className="w-28 bg-transparent text-xs text-slate-800 outline-none placeholder:text-slate-400 dark:text-slate-200 dark:placeholder:text-slate-600"
          />
        </form>
        <button
          onClick={() => flowRef.current?.fitView({ duration: 500, padding: 0.15 })}
          className="inline-flex items-center gap-1 rounded-lg border border-slate-200 px-2 py-1 text-xs text-slate-500 hover:text-slate-900 dark:border-slate-800 dark:text-slate-400 dark:hover:text-slate-200"
        >
          <Maximize2 size={12} /> Fit
        </button>
      </div>

      {error && <div className="text-sm text-risk-critical">{error}</div>}

      <div className="relative flex-1 min-h-[560px] rounded-xl border border-slate-200 overflow-hidden bg-slate-100 shadow-sm dark:border-slate-800 dark:bg-[#04060f] dark:shadow-none">
        {graph && entityCount > 0 ? (
          <ReactFlow
            nodes={nodes}
            edges={edges}
            nodeTypes={cosmosNodeTypes}
            onInit={(inst) => {
              flowRef.current = inst;
            }}
            onNodeClick={handleNodeClick}
            onNodeDoubleClick={handleNodeDoubleClick}
            onPaneClick={() => setSelection(null)}
            fitView
            fitViewOptions={{ padding: 0.12 }}
            minZoom={0.15}
            maxZoom={2.5}
            proOptions={{ hideAttribution: true }}
          >
            <Background color={light ? "#cbd5e1" : "#16213a"} gap={28} variant={BackgroundVariant.Dots} />
            <Controls />
            <MiniMap
              nodeColor={(n) => {
                const kind = (n.data as CosmosNodeData | undefined)?.kind;
                if (kind === "developer") return "#7dd3fc";
                if (kind === "library") return "#c084fc";
                if (kind === "file") return "#64748b";
                if (kind === "module") return RISK_COLOR[riskByNodeId.get(n.id)?.risk_level ?? ""] ?? "#475569";
                return "#1e293b";
              }}
              maskColor={light ? "rgba(241, 245, 249, 0.75)" : "rgba(2, 6, 23, 0.75)"}
              style={light ? { background: "#e2e8f0", border: "1px solid #cbd5e1" } : { background: "#070c18", border: "1px solid #1e293b" }}
            />
            <Panel position="top-left">
              <div className="rounded-lg bg-white/90 border border-slate-200 px-3 py-2 text-[11px] text-slate-600 space-y-1 dark:bg-slate-950/90 dark:border-slate-800 dark:text-slate-400">
                <div className="font-medium text-slate-700 dark:text-slate-300 mb-1">Legend</div>
                <div className="flex items-center gap-1.5">
                  <span className="inline-block h-2.5 w-2.5 rounded-full bg-sky-300" /> Developer (size = knowledge)
                </div>
                {(mode === "ownership"
                  ? (["≤1 sole owner", "2 shared", "3+ spread"] as const)
                  : (["CRITICAL", "HIGH", "MODERATE", "LOW"] as const)
                ).map((l) => (
                  <div key={l} className="flex items-center gap-1.5">
                    <span
                      className="inline-block h-2.5 w-2.5 rounded-sm"
                      style={{
                        background:
                          mode === "ownership"
                            ? l === "≤1 sole owner"
                              ? "#f87171"
                              : l === "2 shared"
                                ? "#facc15"
                                : "#4ade80"
                            : RISK_COLOR[l],
                        opacity: 0.9,
                      }}
                    />
                    Module · {mode === "ownership" ? `bus factor ${l}` : `${l} risk`}
                  </div>
                ))}
                {(showFiles || mode === "contributions") && (
                  <div className="flex items-center gap-1.5">
                    <span className="inline-block h-2 w-4 rounded-sm bg-slate-500" /> File
                  </div>
                )}
                {showLibraries && libraries.length > 0 && (
                  <div className="flex items-center gap-1.5">
                    <span className="inline-block h-2.5 w-2.5 rotate-45 bg-purple-400" /> Third-party library
                  </div>
                )}
                <div className="flex items-center gap-1.5">
                  <span className="inline-block h-0.5 w-4 bg-slate-400" /> knowledge flow (thicker = stronger)
                </div>
                <div className="flex items-center gap-1.5">
                  <span className="inline-block h-0.5 w-4 bg-orange-500" /> depends on
                </div>
              </div>
            </Panel>
          </ReactFlow>
        ) : (
          graph && (
            <div className="h-full flex items-center justify-center text-sm text-slate-500 px-6 text-center">
              {dashboard && dashboard.last_analysis_run_id ? (
                <span>
                  Analysis hasn&apos;t produced graph data — the latest run may have failed. Check the{" "}
                  <Link to={`/projects/${projectId}`} className="text-slate-300 underline hover:text-white">
                    Dashboard
                  </Link>{" "}
                  for the run status and error.
                </span>
              ) : (
                <span>No graph data yet — run analysis from the Dashboard.</span>
              )}
            </div>
          )
        )}
        {!graph && !error && (
          <div className="h-full flex items-center justify-center text-sm text-slate-500">Loading cosmos…</div>
        )}
        {selection && projectId && (
          <DetailPanel
            projectId={projectId}
            selection={selection}
            fileEntry={selection.kind === "file" ? fileById.get(selection.refId) : undefined}
            libEntry={selection.kind === "library" ? libByName.get(selection.refId) : undefined}
            filesExpanded={expandedModules.has(selection.nodeId)}
            onToggleFiles={
              selection.kind === "module"
                ? () =>
                    setExpandedModules((prev) => {
                      const next = new Set(prev);
                      if (next.has(selection.nodeId)) next.delete(selection.nodeId);
                      else next.add(selection.nodeId);
                      return next;
                    })
                : undefined
            }
            onClose={() => setSelection(null)}
          />
        )}
      </div>
    </div>
  );
}
