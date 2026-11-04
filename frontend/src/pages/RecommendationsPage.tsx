import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/services/api";
import type {
  DeveloperSummary,
  KnowledgeTransferPlan,
  ModuleSummary,
  Recommendation,
} from "@/types/api";
import {
  ListChecks,
  BookOpen,
  CheckCircle2,
  Copy,
  X,
  Target,
  Sparkles,
  Layers,
} from "lucide-react";

const SEVERITY_STYLE: Record<string, string> = {
  CRITICAL: "border-risk-critical/40 bg-risk-critical/10 text-risk-critical",
  HIGH: "border-risk-high/40 bg-risk-high/10 text-risk-high",
  MODERATE: "border-risk-moderate/40 bg-risk-moderate/10 text-risk-moderate",
  LOW: "border-risk-low/40 bg-risk-low/10 text-risk-low",
};

const RULE_LABELS: Record<string, string> = {
  LOW_BUS_FACTOR: "Bus Factor Risk",
  HIGH_CONCENTRATION: "Knowledge Concentration",
  MISSING_DOCUMENTATION: "Documentation Deficit",
  HIGH_COMPLEXITY: "High Cyclomatic Complexity",
  HIGH_CHURN: "High Code Churn",
  HIGH_CENTRALITY: "Architectural Bottleneck",
  DRIFT_INCREASING: "Knowledge Drift",
  CRITICAL_KNOWLEDGE_AREA: "Critical System Area",
};

export default function RecommendationsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [recs, setRecs] = useState<Recommendation[] | null>(null);
  const [modules, setModules] = useState<ModuleSummary[]>([]);
  const [developers, setDevelopers] = useState<DeveloperSummary[]>([]);

  // Knowledge Transfer Plan Modal State
  const [showPlanModal, setShowPlanModal] = useState(false);
  const [selectedModuleName, setSelectedModuleName] = useState("");
  const [selectedBackupDev, setSelectedBackupDev] = useState<string>("");
  const [planPriority, setPlanPriority] = useState<string>("HIGH");
  const [planResult, setPlanResult] = useState<KnowledgeTransferPlan | null>(null);
  const [generatingPlan, setGeneratingPlan] = useState(false);
  const [copied, setCopied] = useState(false);

  useEffect(() => {
    if (!projectId) return;
    api.getRecommendations(projectId).then(setRecs);
    api.listModules(projectId).then((m) => {
      setModules(m);
      if (m.length > 0) setSelectedModuleName(m[0].name);
    }).catch(() => {});
    api.listDevelopers(projectId).then(setDevelopers).catch(() => {});
  }, [projectId]);

  const handleOpenPlanForModule = (moduleName: string) => {
    setSelectedModuleName(moduleName);
    setPlanResult(null);
    setShowPlanModal(true);
  };

  const handleGeneratePlan = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId || !selectedModuleName) return;
    setGeneratingPlan(true);
    try {
      const plan = await api.getKnowledgeTransferPlan(
        projectId,
        selectedModuleName,
        selectedBackupDev || null,
        planPriority,
      );
      setPlanResult(plan);
    } catch {
      // fallback local plan
      setPlanResult({
        module: selectedModuleName,
        topics: [
          `${selectedModuleName} architectural design and component boundaries`,
          `Core data models, state management, and persistence for ${selectedModuleName}`,
          `Key operational runbooks and deployment procedures for ${selectedModuleName}`,
          `Common failure modes, error handling, and recovery steps for ${selectedModuleName}`,
          `Critical APIs, dependency contracts, and integration points for ${selectedModuleName}`,
          `Testing strategy, regression suites, and debugging workflows for ${selectedModuleName}`,
        ],
        recommended_backup_developer_id: selectedBackupDev || null,
        priority: planPriority,
        suggested_format: "Pair programming sessions + architectural documentation review",
      });
    } finally {
      setGeneratingPlan(false);
    }
  };

  const copyPlanToClipboard = () => {
    if (!planResult) return;
    const text = [
      `Knowledge Transfer Plan: ${planResult.module} (Priority: ${planResult.priority})`,
      `Suggested Format: ${planResult.suggested_format}`,
      "",
      "Actionable Curriculum & Review Topics:",
      ...planResult.topics.map((t, idx) => `  ${idx + 1}. [ ] ${t}`),
    ].join("\n");
    navigator.clipboard.writeText(text);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  return (
    <div className="space-y-6">
      {/* Header */}
      <div className="flex flex-col sm:flex-row sm:items-center justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">Risk Mitigation &amp; Recommendations</h1>
          <p className="text-xs text-slate-500 mt-1">
            Deterministic, explainable action items derived from repository graph analysis and metric thresholds.
          </p>
        </div>
        <button
          onClick={() => {
            setPlanResult(null);
            setShowPlanModal(true);
          }}
          className="inline-flex items-center gap-2 rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-700 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
        >
          <BookOpen size={16} />
          Knowledge Transfer Plan
        </button>
      </div>

      {recs === null && <div className="text-slate-500 text-sm">Loading recommendations…</div>}

      {recs?.length === 0 && (
        <div className="rounded-xl border border-slate-200 bg-white p-8 text-center text-slate-500 dark:border-slate-800 dark:bg-transparent">
          <ListChecks size={32} className="mx-auto mb-2 opacity-50" />
          <p className="text-sm">No risk recommendations triggered.</p>
          <p className="text-xs text-slate-400 mt-1">
            Run an analysis from the Dashboard or your codebase exhibits balanced ownership and low risk.
          </p>
        </div>
      )}

      {/* Recommendations List */}
      <div className="space-y-4">
        {recs?.map((r) => {
          const ruleLabel = r.rule_type ? RULE_LABELS[r.rule_type] || r.rule_type : null;
          return (
            <div
              key={r.id}
              className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none space-y-3"
            >
              <div className="flex flex-wrap items-center justify-between gap-2">
                <div className="flex items-center gap-2">
                  <span
                    className={`rounded-full border px-2.5 py-0.5 text-xs font-semibold uppercase tracking-wider ${
                      SEVERITY_STYLE[r.severity] ?? "border-slate-800"
                    }`}
                  >
                    {r.severity}
                  </span>
                  {ruleLabel && (
                    <span className="rounded-full bg-slate-100 text-slate-700 dark:bg-slate-800 dark:text-slate-300 px-2.5 py-0.5 text-xs font-medium">
                      {ruleLabel}
                    </span>
                  )}
                  {r.triggering_metric && (
                    <span className="font-mono text-[11px] text-slate-500 bg-slate-50 dark:bg-slate-900 px-2 py-0.5 rounded border border-slate-200 dark:border-slate-800">
                      {r.triggering_metric}
                    </span>
                  )}
                </div>

                {r.module_id && (
                  <button
                    onClick={() => {
                      const mod = modules.find((m) => m.id === r.module_id);
                      if (mod) handleOpenPlanForModule(mod.name);
                    }}
                    className="inline-flex items-center gap-1 text-xs text-slate-500 hover:text-slate-900 dark:hover:text-slate-200"
                  >
                    <BookOpen size={12} /> Plan Transfer &rarr;
                  </button>
                )}
              </div>

              <div className="text-base font-semibold text-slate-900 dark:text-slate-100">
                {r.title}
              </div>

              <div className="text-sm text-slate-600 dark:text-slate-400 leading-relaxed">
                {r.description}
              </div>

              {r.suggested_action && (
                <div className="flex items-start gap-2 bg-slate-50 dark:bg-slate-900/60 border border-slate-200 dark:border-slate-800 rounded-lg p-3 text-xs text-slate-700 dark:text-slate-300">
                  <Target size={14} className="mt-0.5 shrink-0 text-slate-500" />
                  <div>
                    <span className="font-semibold text-slate-900 dark:text-slate-200">
                      Recommended Action:{" "}
                    </span>
                    {r.suggested_action}
                  </div>
                </div>
              )}
            </div>
          );
        })}
      </div>

      {/* Knowledge Transfer Plan Modal */}
      {showPlanModal && (
        <div className="fixed inset-0 z-50 flex items-center justify-center bg-black/50 p-4">
          <div className="max-w-xl w-full rounded-2xl border border-slate-200 bg-white p-6 shadow-xl dark:border-slate-800 dark:bg-slate-900 space-y-5 max-h-[90vh] overflow-y-auto">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-2">
                <BookOpen size={20} className="text-slate-700 dark:text-slate-300" />
                <h3 className="font-semibold text-lg text-slate-900 dark:text-slate-100">
                  Knowledge Transfer Planning
                </h3>
              </div>
              <button
                onClick={() => setShowPlanModal(false)}
                className="text-slate-400 hover:text-slate-600 dark:hover:text-slate-200"
              >
                <X size={18} />
              </button>
            </div>

            <form onSubmit={handleGeneratePlan} className="space-y-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Target Module
                </label>
                {modules.length > 0 ? (
                  <select
                    value={selectedModuleName}
                    onChange={(e) => setSelectedModuleName(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-800"
                  >
                    {modules.map((m) => (
                      <option key={m.id} value={m.name}>
                        {m.name} {m.bus_factor !== null ? `(Bus Factor: ${m.bus_factor})` : ""}
                      </option>
                    ))}
                  </select>
                ) : (
                  <input
                    type="text"
                    value={selectedModuleName}
                    onChange={(e) => setSelectedModuleName(e.target.value)}
                    placeholder="e.g. backend/app/auth"
                    required
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-800"
                  />
                )}
              </div>

              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                <div>
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Assign Backup Maintainer (Optional)
                  </label>
                  <select
                    value={selectedBackupDev}
                    onChange={(e) => setSelectedBackupDev(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-800"
                  >
                    <option value="">Unassigned</option>
                    {developers.map((d) => (
                      <option key={d.id} value={d.id}>
                        {d.display_name}
                      </option>
                    ))}
                  </select>
                </div>
                <div>
                  <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                    Priority Level
                  </label>
                  <select
                    value={planPriority}
                    onChange={(e) => setPlanPriority(e.target.value)}
                    className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-800"
                  >
                    <option value="CRITICAL">Critical</option>
                    <option value="HIGH">High</option>
                    <option value="MODERATE">Moderate</option>
                  </select>
                </div>
              </div>

              <button
                type="submit"
                disabled={generatingPlan || !selectedModuleName}
                className="w-full inline-flex items-center justify-center gap-2 rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
              >
                <Sparkles size={16} />
                {generatingPlan ? "Generating Plan…" : "Generate Structured Transfer Plan"}
              </button>
            </form>

            {planResult && (
              <div className="mt-4 pt-4 border-t border-slate-200 dark:border-slate-800 space-y-4">
                <div className="flex items-center justify-between">
                  <div>
                    <h4 className="text-sm font-semibold text-slate-900 dark:text-slate-100">
                      Curriculum for {planResult.module}
                    </h4>
                    <span className="text-xs text-slate-500">
                      Format: {planResult.suggested_format}
                    </span>
                  </div>
                  <button
                    onClick={copyPlanToClipboard}
                    className="inline-flex items-center gap-1.5 text-xs text-slate-600 hover:text-slate-900 dark:text-slate-400 dark:hover:text-slate-100"
                  >
                    {copied ? <CheckCircle2 size={14} className="text-risk-low" /> : <Copy size={14} />}
                    {copied ? "Copied!" : "Copy Plan"}
                  </button>
                </div>

                <div className="space-y-2">
                  {planResult.topics.map((topic, i) => (
                    <div
                      key={i}
                      className="flex items-start gap-2.5 text-xs text-slate-700 dark:text-slate-300 bg-slate-50 dark:bg-slate-800/60 p-2.5 rounded-lg border border-slate-200 dark:border-slate-700/50"
                    >
                      <Layers size={14} className="text-slate-400 shrink-0 mt-0.5" />
                      <span>{topic}</span>
                    </div>
                  ))}
                </div>
              </div>
            )}
          </div>
        </div>
      )}
    </div>
  );
}
