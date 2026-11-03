import { Handle, Position, type NodeProps } from "reactflow";
import type { CosmosNodeData } from "./cosmosLayout";

function Tooltip({ lines, light }: { lines?: string[]; light?: boolean }) {
  if (!lines || lines.length === 0) return null;
  return (
    <div
      className={`pointer-events-none absolute bottom-full left-1/2 z-50 mb-2 -translate-x-1/2 whitespace-nowrap rounded-lg border px-2.5 py-1.5 text-left text-[11px] leading-relaxed opacity-0 shadow-xl transition-opacity duration-150 group-hover:opacity-100 ${
        light ? "border-slate-200 bg-white text-slate-700" : "border-slate-700 bg-slate-950/95 text-slate-300"
      }`}
    >
      {lines.map((l, i) => (
        <div key={i}>{l}</div>
      ))}
    </div>
  );
}

function dimStyle(dimmed?: boolean): React.CSSProperties {
  return dimmed ? { opacity: 0.12, transition: "opacity 300ms" } : { opacity: 1, transition: "opacity 300ms" };
}

export function DeveloperNode({ data, selected }: NodeProps<CosmosNodeData>) {
  const s = data.size || 48;
  const light = data.light;
  return (
    <div className="group relative" style={{ width: s, height: s, ...dimStyle(data.dimmed) }}>
      <Tooltip lines={[data.label, ...(data.tooltip ?? [])]} light={light} />
      <div
        className="flex h-full w-full items-center justify-center rounded-full font-semibold"
        style={{
          background: light
            ? `radial-gradient(circle at 35% 30%, #ffffff 0%, #e0f2fe 55%, #bae6fd 100%)`
            : `radial-gradient(circle at 35% 30%, #1e3a5f 0%, #0b1a33 55%, #050b1a 100%)`,
          border: `2px solid ${selected ? (light ? "#0284c7" : "#ffffff") : data.color}`,
          boxShadow: selected
            ? `0 0 24px ${data.color}, 0 0 48px ${data.color}66`
            : `0 0 14px ${data.color}55`,
          color: light ? "#0c4a6e" : "#e0f2fe",
          fontSize: s < 52 ? 11 : 13,
        }}
      >
        {data.label.slice(0, 1).toUpperCase()}
      </div>
      <div
        className={`absolute -bottom-5 left-1/2 w-max -translate-x-1/2 text-center text-[10px] ${
          light ? "text-slate-700" : "text-slate-300"
        }`}
        style={light ? undefined : { textShadow: "0 1px 6px #000" }}
      >
        {data.label}
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
    </div>
  );
}

const HEX_CLIP = "polygon(25% 4%, 75% 4%, 100% 50%, 75% 96%, 25% 96%, 0% 50%)";

export function ModuleNode({ data, selected }: NodeProps<CosmosNodeData>) {
  const s = data.size || 120;
  const light = data.light;
  return (
    <div className="group relative" style={{ width: s, height: s, ...dimStyle(data.dimmed) }}>
      <Tooltip lines={[data.label, ...(data.tooltip ?? [])]} light={light} />
      <div
        className={`flex h-full w-full flex-col items-center justify-center px-5 text-center ${
          data.alert ? "cosmos-alert" : ""
        }`}
        style={{
          clipPath: HEX_CLIP,
          background: light
            ? `radial-gradient(circle at 50% 35%, #ffffff 0%, #f1f5f9 60%, #e2e8f0 100%)`
            : `radial-gradient(circle at 50% 35%, #1c2440 0%, #0b1026 60%, #05081a 100%)`,
          border: "none",
          boxShadow: "none",
          color: data.color,
          filter: selected
            ? `drop-shadow(0 0 18px ${data.color})`
            : `drop-shadow(0 0 10px ${data.color}88)`,
          outline: selected ? `2px solid ${light ? "#0f172a" : "#fff"}` : `2px solid ${data.color}`,
          outlineOffset: -2,
        }}
      >
        <div
          className={`font-semibold ${light ? "text-slate-900" : "text-slate-100"}`}
          style={{ fontSize: 13, lineHeight: 1.15 }}
        >
          {data.label}
        </div>
        {data.sub && <div className={`mt-0.5 text-[10px] ${light ? "text-slate-500" : "text-slate-400"}`}>{data.sub}</div>}
      </div>
      {data.expandable && (
        <div
          className="absolute -bottom-1 -right-1 rounded-full border border-slate-600 bg-slate-900 px-1.5 py-px text-[9px] text-slate-300"
          title={data.expanded ? "Files expanded — double-click to collapse" : "Double-click to expand files"}
        >
          {data.expanded ? `▾ ${data.filesShown}/${data.filesTotal}` : `▸ ${data.filesTotal} files`}
        </div>
      )}
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
    </div>
  );
}

export function FileNode({ data, selected }: NodeProps<CosmosNodeData>) {
  const light = data.light;
  return (
    <div className="group relative h-full w-full" style={dimStyle(data.dimmed)}>
      <Tooltip lines={[data.label, ...(data.tooltip ?? [])]} light={light} />
      <div
        className="flex h-full w-full items-center gap-1.5 rounded-md border px-2"
        style={{
          background: light ? "#ffffffee" : "#0d1526ee",
          borderColor: selected ? (light ? "#0f172a" : "#fff") : light ? "#cbd5e1" : "#3b4a63",
          boxShadow: selected ? "0 0 12px #94a3b866" : light ? "0 1px 4px #00000022" : "0 0 6px #00000088",
        }}
      >
        <span className="inline-block h-2 w-2 shrink-0 rounded-full" style={{ background: data.color }} />
        <span className={`truncate text-[11px] ${light ? "text-slate-800" : "text-slate-200"}`}>{data.label}</span>
      </div>
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
    </div>
  );
}

export function LibraryNode({ data, selected }: NodeProps<CosmosNodeData>) {
  const s = data.size || 56;
  const light = data.light;
  return (
    <div
      className="group relative flex flex-col items-center"
      style={{ width: 120, ...dimStyle(data.dimmed) }}
    >
      <Tooltip lines={[data.label, ...(data.tooltip ?? [])]} light={light} />
      <div
        style={{
          width: s,
          height: s,
          transform: "rotate(45deg)",
          borderRadius: 10,
          background: light
            ? "radial-gradient(circle at 35% 30%, #ffffff 0%, #ede9fe 60%, #ddd6fe 100%)"
            : "radial-gradient(circle at 35% 30%, #3b1d5e 0%, #1c1033 60%, #0d0719 100%)",
          border: `2px solid ${selected ? (light ? "#7c3aed" : "#fff") : data.color}`,
          boxShadow: selected ? `0 0 22px ${data.color}` : `0 0 12px ${data.color}66`,
        }}
      />
      <div className={`mt-1 max-w-[120px] truncate text-center text-[10px] ${light ? "text-slate-700" : "text-slate-300"}`}>{data.label}</div>
      {data.sub && <div className="-mt-0.5 text-[9px] text-slate-500">{data.sub}</div>}
      <Handle type="source" position={Position.Right} style={{ opacity: 0 }} />
      <Handle type="target" position={Position.Left} style={{ opacity: 0 }} />
    </div>
  );
}

export function ClusterNode({ data }: NodeProps<CosmosNodeData>) {
  return (
    <div className="pointer-events-none relative h-full w-full" style={dimStyle(data.dimmed)}>
      <div
        className="absolute inset-0 rounded-full"
        style={{
          background: `radial-gradient(circle, ${data.color}14 0%, ${data.color}08 55%, transparent 72%)`,
          border: `1px dashed ${data.color}33`,
        }}
      />
      <div
        className="absolute left-1/2 top-3 -translate-x-1/2 text-[11px] font-medium uppercase tracking-[0.2em]"
        style={{ color: `${data.color}99` }}
      >
        {data.label}
      </div>
    </div>
  );
}

export const cosmosNodeTypes = {
  developer: DeveloperNode,
  module: ModuleNode,
  file: FileNode,
  library: LibraryNode,
  cluster: ClusterNode,
};
