import { useEffect, useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/services/api";
import type { AuditLog, ProjectMember } from "@/types/api";
import {
  Sliders,
  Clock,
  Users,
  ShieldCheck,
  CheckCircle2,
  AlertCircle,
  Trash2,
  UserPlus,
  RefreshCw,
} from "lucide-react";

interface RiskConfigState {
  risk_weights: {
    knowledge_concentration: number;
    bus_factor_risk: number;
    documentation_risk: number;
    complexity_risk: number;
    change_frequency_risk: number;
    dependency_risk: number;
  };
  criticality_threshold: number;
  bus_factor_threshold: number;
  recency_half_life_days: number;
}

const DEFAULT_CONFIG: RiskConfigState = {
  risk_weights: {
    knowledge_concentration: 0.25,
    bus_factor_risk: 0.25,
    documentation_risk: 0.15,
    complexity_risk: 0.15,
    change_frequency_risk: 0.1,
    dependency_risk: 0.1,
  },
  criticality_threshold: 60.0,
  bus_factor_threshold: 2,
  recency_half_life_days: 90,
};

export default function ProjectSettingsPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [activeTab, setActiveTab] = useState<"risk" | "schedule" | "members" | "audit">("risk");

  // Risk configuration state
  const [riskConfig, setRiskConfig] = useState<RiskConfigState>(DEFAULT_CONFIG);
  const [savingRisk, setSavingRisk] = useState(false);
  const [riskSuccess, setRiskSuccess] = useState(false);

  // Schedule state
  const [intervalHours, setIntervalHours] = useState<number>(0);
  const [savingSchedule, setSavingSchedule] = useState(false);
  const [scheduleSuccess, setScheduleSuccess] = useState(false);

  // Members state
  const [members, setMembers] = useState<ProjectMember[]>([]);
  const [newMemberEmail, setNewMemberEmail] = useState("");
  const [newMemberRole, setNewMemberRole] = useState<"owner" | "analyst" | "viewer">("analyst");
  const [addingMember, setAddingMember] = useState(false);

  // Audit logs state
  const [auditLogs, setAuditLogs] = useState<AuditLog[]>([]);
  const [loadingAudit, setLoadingAudit] = useState(false);

  // Generic status
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!projectId) return;

    // Load project info for schedule & risk config
    api
      .getProject(projectId)
      .then((p) => {
        if (p.rescan_interval_hours !== undefined) {
          setIntervalHours(p.rescan_interval_hours);
        }
      })
      .catch((e) => setError(String(e)));

    api
      .getRiskConfig(projectId)
      .then((cfg) => {
        if (cfg && Object.keys(cfg).length > 0) {
          setRiskConfig({
            risk_weights: {
              ...DEFAULT_CONFIG.risk_weights,
              ...((cfg.risk_weights as Record<string, number>) || {}),
            },
            criticality_threshold: (cfg.criticality_threshold as number) ?? DEFAULT_CONFIG.criticality_threshold,
            bus_factor_threshold: (cfg.bus_factor_threshold as number) ?? DEFAULT_CONFIG.bus_factor_threshold,
            recency_half_life_days: (cfg.recency_half_life_days as number) ?? DEFAULT_CONFIG.recency_half_life_days,
          });
        }
      })
      .catch(() => {});

    loadMembers();
  }, [projectId]);

  const loadMembers = () => {
    if (!projectId) return;
    api
      .listProjectMembers(projectId)
      .then(setMembers)
      .catch(() => {});
  };

  const loadAuditLogs = () => {
    if (!projectId) return;
    setLoadingAudit(true);
    api
      .getProjectAuditLogs(projectId)
      .then(setAuditLogs)
      .catch((err) => setError(String(err)))
      .finally(() => setLoadingAudit(false));
  };

  const handleTabChange = (tab: "risk" | "schedule" | "members" | "audit") => {
    setActiveTab(tab);
    setError(null);
    if (tab === "audit") {
      loadAuditLogs();
    } else if (tab === "members") {
      loadMembers();
    }
  };

  const handleSaveRiskConfig = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId) return;
    setSavingRisk(true);
    setError(null);
    setRiskSuccess(false);
    try {
      await api.updateRiskConfig(projectId, riskConfig as unknown as Record<string, unknown>);
      setRiskSuccess(true);
      setTimeout(() => setRiskSuccess(false), 3000);
    } catch (err) {
      setError(String(err));
    } finally {
      setSavingRisk(false);
    }
  };

  const handleSaveSchedule = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId) return;
    setSavingSchedule(true);
    setError(null);
    setScheduleSuccess(false);
    try {
      await api.updateSchedule(projectId, Number(intervalHours));
      setScheduleSuccess(true);
      setTimeout(() => setScheduleSuccess(false), 3000);
    } catch (err) {
      setError(String(err));
    } finally {
      setSavingSchedule(false);
    }
  };

  const handleAddMember = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!projectId || !newMemberEmail.trim()) return;
    setAddingMember(true);
    setError(null);
    try {
      await api.addProjectMember(projectId, newMemberEmail.trim(), newMemberRole);
      setNewMemberEmail("");
      loadMembers();
    } catch (err) {
      setError(String(err));
    } finally {
      setAddingMember(false);
    }
  };

  const handleRemoveMember = async (userId: string, email?: string) => {
    if (!projectId) return;
    if (!window.confirm(`Are you sure you want to remove ${email || "this member"} from the project?`)) return;
    try {
      await api.removeProjectMember(projectId, userId);
      loadMembers();
    } catch (err) {
      setError(String(err));
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="text-xl font-semibold">Project Settings</h1>
        <p className="text-xs text-slate-500 mt-1">
          Configure risk calculation parameters, automated rescan schedules, team access, and view audit events.
        </p>
      </div>

      {error && (
        <div className="flex items-center gap-2 p-3 text-sm text-risk-critical bg-risk-critical/10 border border-risk-critical/30 rounded-lg">
          <AlertCircle size={16} />
          {error}
        </div>
      )}

      {/* Tabs Header */}
      <div className="flex border-b border-slate-200 dark:border-slate-800 gap-4">
        <button
          onClick={() => handleTabChange("risk")}
          className={`flex items-center gap-2 pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "risk"
              ? "border-slate-900 text-slate-900 dark:border-white dark:text-white"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
          }`}
        >
          <Sliders size={16} />
          Risk Configuration
        </button>
        <button
          onClick={() => handleTabChange("schedule")}
          className={`flex items-center gap-2 pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "schedule"
              ? "border-slate-900 text-slate-900 dark:border-white dark:text-white"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
          }`}
        >
          <Clock size={16} />
          Rescan Schedule
        </button>
        <button
          onClick={() => handleTabChange("members")}
          className={`flex items-center gap-2 pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "members"
              ? "border-slate-900 text-slate-900 dark:border-white dark:text-white"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
          }`}
        >
          <Users size={16} />
          Team &amp; Access
        </button>
        <button
          onClick={() => handleTabChange("audit")}
          className={`flex items-center gap-2 pb-3 text-sm font-medium border-b-2 transition-colors ${
            activeTab === "audit"
              ? "border-slate-900 text-slate-900 dark:border-white dark:text-white"
              : "border-transparent text-slate-500 hover:text-slate-700 dark:hover:text-slate-300"
          }`}
        >
          <ShieldCheck size={16} />
          Audit Log
        </button>
      </div>

      {/* TAB 1: Risk Configuration */}
      {activeTab === "risk" && (
        <form onSubmit={handleSaveRiskConfig} className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none space-y-4">
            <h2 className="text-sm font-medium text-slate-900 dark:text-slate-100">Risk Factor Weights (0.0 to 1.0)</h2>
            <p className="text-xs text-slate-500">
              Tune how much each architectural and developer metric contributes to the aggregate module risk score.
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4 pt-2">
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Knowledge Concentration Weight: {riskConfig.risk_weights.knowledge_concentration}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={riskConfig.risk_weights.knowledge_concentration}
                  onChange={(e) =>
                    setRiskConfig({
                      ...riskConfig,
                      risk_weights: {
                        ...riskConfig.risk_weights,
                        knowledge_concentration: parseFloat(e.target.value),
                      },
                    })
                  }
                  className="w-full accent-slate-900 dark:accent-slate-100"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Bus Factor Risk Weight: {riskConfig.risk_weights.bus_factor_risk}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={riskConfig.risk_weights.bus_factor_risk}
                  onChange={(e) =>
                    setRiskConfig({
                      ...riskConfig,
                      risk_weights: {
                        ...riskConfig.risk_weights,
                        bus_factor_risk: parseFloat(e.target.value),
                      },
                    })
                  }
                  className="w-full accent-slate-900 dark:accent-slate-100"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Documentation Risk Weight: {riskConfig.risk_weights.documentation_risk}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={riskConfig.risk_weights.documentation_risk}
                  onChange={(e) =>
                    setRiskConfig({
                      ...riskConfig,
                      risk_weights: {
                        ...riskConfig.risk_weights,
                        documentation_risk: parseFloat(e.target.value),
                      },
                    })
                  }
                  className="w-full accent-slate-900 dark:accent-slate-100"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Complexity Risk Weight: {riskConfig.risk_weights.complexity_risk}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={riskConfig.risk_weights.complexity_risk}
                  onChange={(e) =>
                    setRiskConfig({
                      ...riskConfig,
                      risk_weights: {
                        ...riskConfig.risk_weights,
                        complexity_risk: parseFloat(e.target.value),
                      },
                    })
                  }
                  className="w-full accent-slate-900 dark:accent-slate-100"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Change Frequency Risk Weight: {riskConfig.risk_weights.change_frequency_risk}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={riskConfig.risk_weights.change_frequency_risk}
                  onChange={(e) =>
                    setRiskConfig({
                      ...riskConfig,
                      risk_weights: {
                        ...riskConfig.risk_weights,
                        change_frequency_risk: parseFloat(e.target.value),
                      },
                    })
                  }
                  className="w-full accent-slate-900 dark:accent-slate-100"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Dependency Risk Weight: {riskConfig.risk_weights.dependency_risk}
                </label>
                <input
                  type="range"
                  min="0"
                  max="1"
                  step="0.05"
                  value={riskConfig.risk_weights.dependency_risk}
                  onChange={(e) =>
                    setRiskConfig({
                      ...riskConfig,
                      risk_weights: {
                        ...riskConfig.risk_weights,
                        dependency_risk: parseFloat(e.target.value),
                      },
                    })
                  }
                  className="w-full accent-slate-900 dark:accent-slate-100"
                />
              </div>
            </div>
          </div>

          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none space-y-4">
            <h2 className="text-sm font-medium text-slate-900 dark:text-slate-100">Thresholds &amp; Decay Parameters</h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Criticality Threshold (0 - 100)
                </label>
                <input
                  type="number"
                  min="10"
                  max="100"
                  value={riskConfig.criticality_threshold}
                  onChange={(e) =>
                    setRiskConfig({
                      ...riskConfig,
                      criticality_threshold: parseFloat(e.target.value) || 60,
                    })
                  }
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-900"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Bus Factor Warning Threshold
                </label>
                <input
                  type="number"
                  min="1"
                  max="10"
                  value={riskConfig.bus_factor_threshold}
                  onChange={(e) =>
                    setRiskConfig({
                      ...riskConfig,
                      bus_factor_threshold: parseInt(e.target.value, 10) || 2,
                    })
                  }
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-900"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">
                  Recency Half-Life (days)
                </label>
                <input
                  type="number"
                  min="14"
                  max="730"
                  value={riskConfig.recency_half_life_days}
                  onChange={(e) =>
                    setRiskConfig({
                      ...riskConfig,
                      recency_half_life_days: parseInt(e.target.value, 10) || 90,
                    })
                  }
                  className="w-full rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-900"
                />
              </div>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={savingRisk}
              className="inline-flex items-center gap-2 rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
            >
              {savingRisk ? <RefreshCw size={14} className="animate-spin" /> : null}
              {savingRisk ? "Saving…" : "Save Risk Configuration"}
            </button>
            {riskSuccess && (
              <span className="flex items-center gap-1 text-xs text-risk-low font-medium">
                <CheckCircle2 size={14} /> Saved successfully
              </span>
            )}
          </div>
        </form>
      )}

      {/* TAB 2: Rescan Schedule */}
      {activeTab === "schedule" && (
        <form onSubmit={handleSaveSchedule} className="space-y-6">
          <div className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none space-y-4">
            <h2 className="text-sm font-medium text-slate-900 dark:text-slate-100">Automated Rescan Schedule</h2>
            <p className="text-xs text-slate-500">
              Configure automatic background repository reconciliation and metric re-evaluation.
            </p>
            <div className="space-y-3 pt-2">
              <label className="flex items-center gap-3 text-sm cursor-pointer">
                <input
                  type="radio"
                  name="schedule"
                  value={0}
                  checked={intervalHours === 0}
                  onChange={() => setIntervalHours(0)}
                  className="accent-slate-900 dark:accent-slate-100"
                />
                <span>Manual only (no automated scans)</span>
              </label>
              <label className="flex items-center gap-3 text-sm cursor-pointer">
                <input
                  type="radio"
                  name="schedule"
                  value={24}
                  checked={intervalHours === 24}
                  onChange={() => setIntervalHours(24)}
                  className="accent-slate-900 dark:accent-slate-100"
                />
                <span>Daily (every 24 hours)</span>
              </label>
              <label className="flex items-center gap-3 text-sm cursor-pointer">
                <input
                  type="radio"
                  name="schedule"
                  value={168}
                  checked={intervalHours === 168}
                  onChange={() => setIntervalHours(168)}
                  className="accent-slate-900 dark:accent-slate-100"
                />
                <span>Weekly (every 7 days / 168 hours)</span>
              </label>
            </div>
          </div>

          <div className="flex items-center gap-3">
            <button
              type="submit"
              disabled={savingSchedule}
              className="inline-flex items-center gap-2 rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
            >
              {savingSchedule ? <RefreshCw size={14} className="animate-spin" /> : null}
              {savingSchedule ? "Saving…" : "Save Schedule"}
            </button>
            {scheduleSuccess && (
              <span className="flex items-center gap-1 text-xs text-risk-low font-medium">
                <CheckCircle2 size={14} /> Schedule updated
              </span>
            )}
          </div>
        </form>
      )}

      {/* TAB 3: Team & Access */}
      {activeTab === "members" && (
        <div className="space-y-6">
          <form
            onSubmit={handleAddMember}
            className="rounded-xl border border-slate-200 bg-white p-5 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none space-y-4"
          >
            <h2 className="text-sm font-medium text-slate-900 dark:text-slate-100">Add Team Member</h2>
            <div className="flex flex-col sm:flex-row gap-3">
              <input
                type="email"
                placeholder="User email address"
                value={newMemberEmail}
                onChange={(e) => setNewMemberEmail(e.target.value)}
                required
                className="flex-1 rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-900"
              />
              <select
                value={newMemberRole}
                onChange={(e) => setNewMemberRole(e.target.value as "owner" | "analyst" | "viewer")}
                className="rounded-lg border border-slate-200 bg-slate-50 px-3 py-2 text-sm dark:border-slate-800 dark:bg-slate-900"
              >
                <option value="viewer">Viewer (Read-only)</option>
                <option value="analyst">Analyst (Run scans, simulations)</option>
                <option value="owner">Owner (Full admin rights)</option>
              </select>
              <button
                type="submit"
                disabled={addingMember}
                className="inline-flex items-center justify-center gap-2 rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
              >
                <UserPlus size={16} />
                {addingMember ? "Adding…" : "Add Member"}
              </button>
            </div>
          </form>

          <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none">
            <div className="px-5 py-3 border-b border-slate-200 dark:border-slate-800 font-medium text-sm">
              Current Members ({members.length})
            </div>
            {members.length === 0 ? (
              <div className="p-6 text-sm text-slate-500">
                No explicit members assigned. (All authenticated users have access until members are assigned).
              </div>
            ) : (
              <div className="divide-y divide-slate-200 dark:divide-slate-800">
                {members.map((m) => (
                  <div key={m.user_id} className="flex items-center justify-between px-5 py-3 text-sm">
                    <div>
                      <div className="font-medium text-slate-900 dark:text-slate-100">
                        {m.full_name || m.email || m.user_id}
                      </div>
                      {m.email && m.full_name && <div className="text-xs text-slate-500">{m.email}</div>}
                    </div>
                    <div className="flex items-center gap-4">
                      <span className="inline-flex items-center px-2.5 py-0.5 rounded-full text-xs font-medium uppercase bg-slate-100 text-slate-800 dark:bg-slate-800 dark:text-slate-200">
                        {m.role}
                      </span>
                      <button
                        onClick={() => handleRemoveMember(m.user_id, m.email)}
                        className="text-slate-400 hover:text-risk-critical transition-colors"
                        title="Remove member"
                      >
                        <Trash2 size={16} />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {/* TAB 4: Audit Log */}
      {activeTab === "audit" && (
        <div className="rounded-xl border border-slate-200 bg-white overflow-hidden shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none">
          <div className="flex items-center justify-between px-5 py-3 border-b border-slate-200 dark:border-slate-800">
            <span className="font-medium text-sm">Project Audit Trail</span>
            <button
              onClick={loadAuditLogs}
              disabled={loadingAudit}
              className="text-xs text-slate-500 hover:text-slate-900 dark:hover:text-slate-200 inline-flex items-center gap-1"
            >
              <RefreshCw size={12} className={loadingAudit ? "animate-spin" : ""} /> Refresh
            </button>
          </div>
          {loadingAudit ? (
            <div className="p-6 text-sm text-slate-500">Loading audit logs…</div>
          ) : auditLogs.length === 0 ? (
            <div className="p-6 text-sm text-slate-500">No audit events recorded for this project yet.</div>
          ) : (
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs text-slate-600 dark:text-slate-300">
                <thead className="bg-slate-50 border-b border-slate-200 text-slate-500 uppercase font-semibold dark:bg-slate-900 dark:border-slate-800">
                  <tr>
                    <th className="px-4 py-3">Timestamp</th>
                    <th className="px-4 py-3">Action</th>
                    <th className="px-4 py-3">Actor</th>
                    <th className="px-4 py-3">Resource</th>
                    <th className="px-4 py-3">Details</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-200 dark:divide-slate-800 font-mono">
                  {auditLogs.map((log) => (
                    <tr key={log.id} className="hover:bg-slate-50/50 dark:hover:bg-slate-900/50">
                      <td className="px-4 py-2.5 whitespace-nowrap">
                        {new Date(log.created_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-2.5 font-semibold text-slate-900 dark:text-slate-100">
                        {log.action}
                      </td>
                      <td className="px-4 py-2.5">
                        {log.actor_email || log.actor_id || "System / Anonymous"}
                      </td>
                      <td className="px-4 py-2.5">
                        {log.resource_type}
                        {log.resource_id ? `:${log.resource_id.slice(0, 8)}` : ""}
                      </td>
                      <td className="px-4 py-2.5 max-w-xs truncate" title={JSON.stringify(log.details)}>
                        {JSON.stringify(log.details)}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
