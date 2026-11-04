import type {
  AnalysisComparison,
  AnalysisRun,
  AuditLog,
  DashboardData,
  DeveloperDetail,
  DeveloperSummary,
  KnowledgeGraphData,
  KnowledgeTransferPlan,
  LibraryEntry,
  ModuleDetail,
  ModuleSummary,
  Project,
  ProjectFile,
  ProjectMember,
  Recommendation,
  RiskEntry,
  SimulationResult,
  Token,
  User,
} from "@/types/api";

const BASE = "/api";

function getAuthHeader(): Record<string, string> {
  const token = localStorage.getItem("coderadar_token");
  return token ? { Authorization: `Bearer ${token}` } : {};
}

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const headers = {
    "Content-Type": "application/json",
    ...getAuthHeader(),
    ...(options?.headers || {}),
  };

  const res = await fetch(`${BASE}${path}`, {
    ...options,
    headers,
  });
  if (!res.ok) {
    let detail = res.statusText;
    try {
      const body = await res.json();
      detail = body.detail ?? detail;
    } catch {
      // ignore
    }
    throw new Error(detail);
  }
  if (res.status === 204) return undefined as T;
  return res.json() as Promise<T>;
}

export const api = {
  // Auth
  register: (payload: { email: string; password: string; full_name?: string }) =>
    request<Token>("/auth/register", { method: "POST", body: JSON.stringify(payload) }),
  login: (payload: { email: string; password: string }) =>
    request<Token>("/auth/login", { method: "POST", body: JSON.stringify(payload) }),
  getMe: () => request<User>("/auth/me"),

  // Project Members & Audit
  listProjectMembers: (projectId: string) => request<ProjectMember[]>(`/projects/${projectId}/members`),
  addProjectMember: (projectId: string, email: string, role: string) =>
    request<ProjectMember>(`/projects/${projectId}/members`, {
      method: "POST",
      body: JSON.stringify({ email, role }),
    }),
  removeProjectMember: (projectId: string, userId: string) =>
    request<void>(`/projects/${projectId}/members/${userId}`, { method: "DELETE" }),
  getProjectAuditLogs: (projectId: string) => request<AuditLog[]>(`/projects/${projectId}/audit-logs`),

  // Projects
  ensureDemo: () =>
    request<{ project_id: string; analysis_run_id: string | null; status: string; created: boolean }>(
      "/demo/ensure",
      { method: "POST" },
    ),
  createProject: (name: string, description?: string, riskConfig?: Record<string, unknown>) =>
    request<Project>("/projects", {
      method: "POST",
      body: JSON.stringify({ name, description, risk_config: riskConfig }),
    }),
  listProjects: () => request<Project[]>("/projects"),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  addRepository: (projectId: string, url: string, provider: string) =>
    request(`/projects/${projectId}/repositories`, {
      method: "POST",
      body: JSON.stringify({ url, provider }),
    }),

  // Analysis & Rescan
  startAnalysis: (
    projectId: string,
    scanMode: "quick" | "full" | "incremental" = "full",
    rescanType = "manual",
    forceFull = false,
  ) =>
    request<AnalysisRun>(
      `/projects/${projectId}/analyze?scan_mode=${scanMode}&rescan_type=${rescanType}`,
      {
        method: "POST",
        body: JSON.stringify({ scan_mode: scanMode, force_full_rescan: forceFull }),
      },
    ),
  getAnalysisRun: (projectId: string, runId: string) =>
    request<AnalysisRun>(`/projects/${projectId}/analysis-runs/${runId}`),
  listAnalysisRuns: (projectId: string) =>
    request<AnalysisRun[]>(`/projects/${projectId}/analysis-runs`),
  cancelAnalysisRun: (projectId: string, runId: string) =>
    request<AnalysisRun>(`/projects/${projectId}/analysis-runs/${runId}/cancel`, { method: "POST" }),
  compareRuns: (projectId: string, baseRunId: string, targetRunId: string) =>
    request<AnalysisComparison>(`/projects/${projectId}/analysis-runs/${baseRunId}/compare/${targetRunId}`),

  // Risk Configuration & Schedule
  getRiskConfig: (projectId: string) => request<Record<string, unknown>>(`/projects/${projectId}/risk-config`),
  updateRiskConfig: (projectId: string, payload: Record<string, unknown>) =>
    request<Record<string, unknown>>(`/projects/${projectId}/risk-config`, {
      method: "PATCH",
      body: JSON.stringify(payload),
    }),
  updateSchedule: (projectId: string, intervalHours: number) =>
    request<{ rescan_interval_hours: number }>(
      `/projects/${projectId}/schedule?interval_hours=${intervalHours}`,
      { method: "PATCH" },
    ),

  // Analytics & Detail
  getDashboard: (projectId: string) => request<DashboardData>(`/projects/${projectId}/dashboard`),
  listDevelopers: (projectId: string) => request<DeveloperSummary[]>(`/projects/${projectId}/developers`),
  getDeveloper: (id: string) => request<DeveloperDetail>(`/developers/${id}`),
  listModules: (projectId: string) => request<ModuleSummary[]>(`/projects/${projectId}/modules`),
  getModule: (id: string) => request<ModuleDetail>(`/modules/${id}`),
  listFiles: (projectId: string, limit = 150) =>
    request<ProjectFile[]>(`/projects/${projectId}/files?limit=${limit}`),
  listLibraries: (projectId: string) => request<LibraryEntry[]>(`/projects/${projectId}/libraries`),
  getKnowledgeGraph: (projectId: string, params?: { developer_id?: string; module_id?: string }) => {
    const clean = Object.fromEntries(
      Object.entries(params ?? {}).filter(([, v]) => v !== undefined && v !== null && v !== ""),
    );
    const qs = new URLSearchParams(clean as Record<string, string>).toString();
    return request<KnowledgeGraphData>(`/projects/${projectId}/knowledge-graph${qs ? `?${qs}` : ""}`);
  },
  getRisks: (projectId: string) => request<RiskEntry[]>(`/projects/${projectId}/risks`),
  getResilience: (projectId: string) =>
    request<{ score: number | null; label: string | null; component_breakdown: unknown }>(
      `/projects/${projectId}/resilience`,
    ),
  getRecommendations: (projectId: string) => request<Recommendation[]>(`/projects/${projectId}/recommendations`),
  getKnowledgeTransferPlan: (
    projectId: string,
    moduleName: string,
    backupDeveloperId?: string | null,
    priority = "HIGH",
  ) =>
    request<KnowledgeTransferPlan>(`/projects/${projectId}/knowledge-transfer-plan`, {
      method: "POST",
      body: JSON.stringify({
        module_name: moduleName,
        backup_developer_id: backupDeveloperId ?? null,
        priority,
      }),
    }),
  getExportUrl: (projectId: string, runId: string, format: "json" | "csv" = "json") =>
    `${BASE}/projects/${projectId}/analysis-runs/${runId}/export?format=${format}`,
  simulateUnavailability: (projectId: string, developerIds: string[]) =>
    request<SimulationResult>("/simulations/developer-unavailability", {
      method: "POST",
      body: JSON.stringify(
        developerIds.length === 1
          ? { project_id: projectId, developer_id: developerIds[0] }
          : { project_id: projectId, developer_ids: developerIds },
      ),
    }),
};
