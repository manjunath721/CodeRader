import type { Edge, Node } from "reactflow";
import type { KnowledgeGraphData, LibraryEntry, ModuleSummary, ProjectFile } from "@/types/api";

export type CosmosMode = "knowledge" | "dependencies" | "ownership" | "contributions" | "risk";

export type CosmosNodeKind = "developer" | "module" | "file" | "library" | "cluster";

export interface CosmosNodeData extends Record<string, unknown> {
  kind: CosmosNodeKind;
  label: string;
  sub?: string;
  /** Accent color (risk / language / neutral). */
  color: string;
  /** Diameter in px for circle/hexagon/diamond shapes. */
  size: number;
  dimmed?: boolean;
  /** Pulsing alert ring (high/critical risk in Risk mode). */
  alert?: boolean;
  tooltip?: string[];
  /** Module file expansion. */
  expandable?: boolean;
  expanded?: boolean;
  filesTotal?: number;
  filesShown?: number;
  /** Raw entity id for navigation (uuid without prefix, or library name). */
  refId?: string;
  /** Light UI theme — node bodies render light surfaces + dark text. */
  light?: boolean;
}

export interface CosmosInput {
  graph: KnowledgeGraphData;
  riskByNodeId: Map<string, ModuleSummary>;
  files: ProjectFile[];
  libraries: LibraryEntry[];
  /** module name -> graph node id (`mod:<uuid>`). */
  moduleNodeByName: Map<string, string>;
  mode: CosmosMode;
  showFiles: boolean;
  showLibraries: boolean;
  expandedModules: Set<string>;
  selectedId: string | null;
  /** Light UI theme — softens canvas chrome (node bodies carry their own flag). */
  light: boolean;
}

export const RISK_COLOR: Record<string, string> = {
  LOW: "#4ade80",
  MODERATE: "#facc15",
  HIGH: "#fb923c",
  CRITICAL: "#f87171",
};

const DEV_COLOR = "#7dd3fc";
const FILE_COLOR = "#94a3b8";
const LIB_COLOR = "#c084fc";
const DEP_EDGE = "#f97316";

const MAX_FILES_PER_MODULE = 12;

function ringPosition(cx: number, cy: number, radius: number, angle: number) {
  return { x: cx + radius * Math.cos(angle), y: cy + radius * Math.sin(angle) };
}

export function buildCosmos(input: CosmosInput): { nodes: Node<CosmosNodeData>[]; edges: Edge[] } {
  const { graph, mode, showFiles, showLibraries } = input;
  const nodes: Node<CosmosNodeData>[] = [];
  const edges: Edge[] = [];
  let edgeSeq = 0;
  const pushEdge = (e: Omit<Edge, "id">) => edges.push({ ...e, id: `e${edgeSeq++}` });

  const devNodes = graph.nodes.filter((n) => n.type === "Developer");
  const modNodes = graph.nodes.filter((n) => n.type === "Module");

  // Knowledge totals per developer + primary cluster (module of max score).
  const knowledgeByDev = new Map<string, { total: number; modules: number; primary: string | null; best: number }>();
  for (const e of graph.edges) {
    if (e.relation !== "contributes_to") continue;
    const cur = knowledgeByDev.get(e.source) ?? { total: 0, modules: 0, primary: null, best: -1 };
    cur.total += e.weight;
    cur.modules += 1;
    if (e.weight > cur.best) {
      cur.best = e.weight;
      cur.primary = e.target;
    }
    knowledgeByDev.set(e.source, cur);
  }

  const showDevs = mode !== "dependencies";
  const hideKnowledgeEdges = mode === "dependencies";
  // Stabilize clusters: highest-risk / most-connected modules first.
  const degree = new Map<string, number>();
  for (const e of graph.edges) {
    degree.set(e.source, (degree.get(e.source) ?? 0) + 1);
    degree.set(e.target, (degree.get(e.target) ?? 0) + 1);
  }
  const riskRank = (id: string) =>
    ({ CRITICAL: 0, HIGH: 1, MODERATE: 2, LOW: 3 })[input.riskByNodeId.get(id)?.risk_level ?? ""] ?? 4;
  const orderedMods = [...modNodes].sort(
    (a, b) => riskRank(a.id) - riskRank(b.id) || (degree.get(b.id) ?? 0) - (degree.get(a.id) ?? 0),
  );

  const clusterRadius = Math.max(430, 170 * Math.sqrt(Math.max(1, orderedMods.length)));
  const clusterByModule = new Map<string, { x: number; y: number }>();
  orderedMods.forEach((m, i) => {
    const angle = -Math.PI / 2 + (i / Math.max(1, orderedMods.length)) * Math.PI * 2;
    clusterByModule.set(m.id, ringPosition(0, 0, clusterRadius, angle));
  });

  // Neighborhood for focus-dim.
  const neighbors = new Set<string>();
  if (input.selectedId) {
    neighbors.add(input.selectedId);
    for (const e of graph.edges) {
      if (e.source === input.selectedId) neighbors.add(e.target);
      if (e.target === input.selectedId) neighbors.add(e.source);
    }
  }
  const dimmed = (id: string) => input.selectedId !== null && !neighbors.has(id);

  // --- Backdrop clusters + module hexagons ---
  const membersByModule = new Map<string, string[]>();
  if (showDevs) {
    for (const d of devNodes) {
      const primary = knowledgeByDev.get(d.id)?.primary;
      if (primary && clusterByModule.has(primary)) {
        const list = membersByModule.get(primary) ?? [];
        list.push(d.id);
        membersByModule.set(primary, list);
      }
    }
  }
  // Sort members by knowledge desc so leads sit closest to the module.
  for (const [mid, members] of membersByModule) {
    members.sort(
      (a, b) => (knowledgeByDev.get(b)?.total ?? 0) - (knowledgeByDev.get(a)?.total ?? 0) || a.localeCompare(b),
    );
    membersByModule.set(mid, members);
  }

  for (const m of orderedMods) {
    const c = clusterByModule.get(m.id)!;
    const risk = input.riskByNodeId.get(m.id);
    const riskColor = RISK_COLOR[risk?.risk_level ?? ""] ?? "#475569";
    const expanded = showFiles && input.expandedModules.has(m.id);
    const backdropR = expanded ? 400 : 265;

    nodes.push({
      id: `cluster:${m.id}`,
      type: "cluster",
      position: { x: c.x - backdropR, y: c.y - backdropR },
      draggable: false,
      selectable: false,
      style: { width: backdropR * 2, height: backdropR * 2, zIndex: -1 },
      data: {
        kind: "cluster",
        label: `${m.label} area`,
        color: mode === "risk" || mode === "ownership" ? riskColor : "#38bdf8",
        size: backdropR * 2,
        dimmed: dimmed(m.id),
      },
    });

    const deg = degree.get(m.id) ?? 0;
    const hexSize = 120 + Math.min(56, deg * 6);
    let sub = risk?.risk_level ? `${risk.risk_level} · ${risk.risk_score}` : "unscored";
    let accent = riskColor;
    if (mode === "ownership") {
      // Ownership mode: color encodes bus factor instead of risk.
      const bf = risk?.bus_factor;
      sub = bf != null ? `bus factor ${bf}` : "bus factor ?";
      accent = bf == null ? "#475569" : bf <= 1 ? "#f87171" : bf === 2 ? "#facc15" : "#4ade80";
    }
    const moduleFiles = input.files.filter((f) => f.module_name === m.label);
    nodes.push({
      id: m.id,
      type: "module",
      position: { x: c.x - hexSize / 2, y: c.y - hexSize / 2 },
      style: { width: hexSize, height: hexSize },
      data: {
        kind: "module",
        label: m.label,
        sub,
        color: accent,
        size: hexSize,
        dimmed: dimmed(m.id),
        alert: mode === "risk" && (risk?.risk_level === "HIGH" || risk?.risk_level === "CRITICAL"),
        tooltip: [
          `Risk ${risk?.risk_score ?? "—"} (${risk?.risk_level ?? "unscored"})`,
          `Bus factor ${risk?.bus_factor ?? "—"} · concentration ${risk?.concentration_pct ?? "—"}%`,
          `${deg} graph relationships`,
        ],
        expandable: showFiles && moduleFiles.length > 0,
        expanded,
        filesTotal: moduleFiles.length,
        filesShown: expanded ? Math.min(MAX_FILES_PER_MODULE, moduleFiles.length) : 0,
        refId: m.id.replace(/^mod:/, ""),
      },
    });

    // Orbiting developers (skip in Dependencies mode).
    if (showDevs) {
      const members = membersByModule.get(m.id) ?? [];
      const outward = Math.atan2(c.y, c.x);
      members.forEach((devId, i) => {
        const dev = devNodes.find((d) => d.id === devId)!;
        const stat = knowledgeByDev.get(devId);
        const spread = members.length <= 1 ? 0 : (i / (members.length - 1) - 0.5) * Math.PI * 1.1;
        const p = ringPosition(c.x, c.y, 195, outward + spread);
        const devSize =
          mode === "contributions"
            ? 44 + Math.min(40, (stat?.modules ?? 0) * 10)
            : 44 + Math.min(44, (stat?.total ?? 0) / 9);
        nodes.push({
          id: devId,
          type: "developer",
          position: { x: p.x - devSize / 2, y: p.y - devSize / 2 },
          style: { width: devSize, height: devSize },
          data: {
            kind: "developer",
            label: dev.label,
            sub: `${stat?.modules ?? 0} mod · ${Math.round(stat?.total ?? 0)} knowl.`,
            color: DEV_COLOR,
            size: devSize,
            dimmed: dimmed(devId),
            tooltip: [`${stat?.modules ?? 0} modules · ${Math.round(stat?.total ?? 0)} total knowledge`],
            refId: devId.replace(/^dev:/, ""),
          },
        });
      });
    }

    // Expanded file ring.
    if (expanded) {
      const shown = moduleFiles.slice(0, MAX_FILES_PER_MODULE);
      shown.forEach((f, i) => {
        const p = ringPosition(c.x, c.y, 305, (i / shown.length) * Math.PI * 2 - Math.PI / 2);
        const fid = `file:${f.id}`;
        nodes.push({
          id: fid,
          type: "file",
          position: { x: p.x - 70, y: p.y - 17 },
          style: { width: 140, height: 34 },
          data: {
            kind: "file",
            label: f.name,
            sub: f.language ?? "",
            color: FILE_COLOR,
            size: 34,
            dimmed: dimmed(fid) || dimmed(m.id),
            tooltip: [f.path, `${f.language ?? "?"} · ${(f.size_bytes / 1024).toFixed(1)} KB · complexity ${f.complexity}`],
            refId: f.id,
          },
        });
        neighbors.add(m.id);
        neighbors.add(fid);
        pushEdge({
          source: m.id,
          target: fid,
          type: "default",
          animated: false,
          style: { stroke: "#475569", strokeWidth: 1, strokeDasharray: "4 4", opacity: 0.7 },
        });
      });
    }
  }

  // Unassigned developers drift on an outer orbit.
  if (showDevs) {
    const assigned = new Set<string>();
    for (const list of membersByModule.values()) for (const id of list) assigned.add(id);
    const drifters = devNodes.filter((d) => !assigned.has(d.id));
    drifters.forEach((d, i) => {
      const p = ringPosition(0, 0, clusterRadius + 300, Math.PI * 0.75 + (i / Math.max(1, drifters.length)) * Math.PI * 0.5);
      nodes.push({
        id: d.id,
        type: "developer",
        position: { x: p.x - 22, y: p.y - 22 },
        style: { width: 44, height: 44 },
        data: {
          kind: "developer",
          label: d.label,
          color: DEV_COLOR,
          size: 44,
          dimmed: dimmed(d.id),
          refId: d.id.replace(/^dev:/, ""),
        },
      });
    });
  }

  // Library diamonds on the far orbit (links resolved before dimming is evaluated).
  const shownLibs = showLibraries && mode !== "ownership" ? input.libraries.slice(0, 24) : [];
  const libTargets = new Map<string, string[]>();
  for (const lib of shownLibs) {
    const targets: string[] = [];
    for (const modName of lib.used_by_modules) {
      const target = input.moduleNodeByName.get(modName);
      if (target) {
        targets.push(target);
        neighbors.add(`lib:${lib.name}`);
        neighbors.add(target);
      }
    }
    libTargets.set(lib.name, targets);
  }
  if (shownLibs.length > 0) {
    shownLibs.forEach((lib, i) => {
      const p = ringPosition(0, 0, clusterRadius + 560, (i / Math.max(1, shownLibs.length)) * Math.PI * 2);
      const lid = `lib:${lib.name}`;
      const size = 40 + Math.min(36, lib.file_count * 4);
      nodes.push({
        id: lid,
        type: "library",
        position: { x: p.x - 60, y: p.y - 30 },
        style: { width: 120, height: 60 },
        data: {
          kind: "library",
          label: lib.name,
          sub: `${lib.file_count} files`,
          color: LIB_COLOR,
          size,
          dimmed: dimmed(lid),
          tooltip: [`Used by: ${lib.used_by_modules.join(", ") || "—"}`],
          refId: lib.name,
        },
      });
      for (const target of libTargets.get(lib.name) ?? []) {
        const hot = input.selectedId !== null && (target === input.selectedId || lid === input.selectedId);
        pushEdge({
          source: target,
          target: lid,
          type: "default",
          animated: hot,
          label: "uses",
          labelStyle: { fontSize: 9, fill: "#c084fc" },
          labelBgStyle: { fill: input.light ? "#ffffff" : "#020617" },
          style: {
            stroke: LIB_COLOR,
            strokeWidth: 1.5,
            strokeDasharray: "6 4",
            opacity: hot ? 1 : input.selectedId !== null && !hot ? 0.08 : 0.55,
          },
        });
      }
    });
  }

  // Core edges.
  for (const e of graph.edges) {
    if (e.relation === "contributes_to" && (hideKnowledgeEdges || !showDevs)) continue;
    if (e.relation === "depends_on" && mode === "ownership") continue;
    const isDep = e.relation === "depends_on";
    const hot = input.selectedId !== null && (e.source === input.selectedId || e.target === input.selectedId);
    const important = isDep || e.weight >= 50;
    const baseOpacity =
      mode === "risk"
        ? isDep
          ? 0.9
          : 0.3
        : isDep
          ? 0.85
          : Math.max(0.22, e.weight / 100);
    pushEdge({
      source: e.source,
      target: e.target,
      type: "default",
      animated: important && (hot || input.selectedId === null),
      label: isDep ? "depends on" : undefined,
      labelStyle: { fontSize: 9, fill: input.light ? "#64748b" : "#94a3b8" },
      labelBgStyle: { fill: input.light ? "#ffffff" : "#020617" },
      style: {
        stroke: isDep ? DEP_EDGE : "#94a3b8",
        strokeWidth: isDep ? 2.2 : 1 + (e.weight / 100) * 3.5,
        opacity: input.selectedId !== null && !hot ? 0.07 : baseOpacity,
        filter: hot ? "drop-shadow(0 0 6px rgba(125,211,252,.9))" : undefined,
      },
    });
  }

  for (const n of nodes) n.data.light = input.light;
  return { nodes, edges };
}
