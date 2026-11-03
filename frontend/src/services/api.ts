import type {
  AIQueryResponse,
  AnalysisRun,
  DashboardData,
  DeveloperDetail,
  DeveloperSummary,
  KnowledgeGraphData,
  LibraryEntry,
  ModuleDetail,
  ModuleSummary,
  Project,
  ProjectFile,
  Recommendation,
  RiskEntry,
  SimulationResult,
} from "@/types/api";

const BASE = "/api";

async function request<T>(path: string, options?: RequestInit): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...options,
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
  ensureDemo: () =>
    request<{ project_id: string; analysis_run_id: string | null; status: string; created: boolean }>(
      "/demo/ensure",
      { method: "POST" },
    ),
  createProject: (name: string, description?: string) =>
    request<Project>("/projects", { method: "POST", body: JSON.stringify({ name, description }) }),
  listProjects: () => request<Project[]>("/projects"),
  deleteProject: (id: string) => request<void>(`/projects/${id}`, { method: "DELETE" }),
  getProject: (id: string) => request<Project>(`/projects/${id}`),
  addRepository: (projectId: string, url: string, provider: string) =>
    request(`/projects/${projectId}/repositories`, {
      method: "POST",
      body: JSON.stringify({ url, provider }),
    }),
  startAnalysis: (projectId: string, scanMode: "quick" | "full" = "full") =>
    request<AnalysisRun>(`/projects/${projectId}/analyze?scan_mode=${scanMode}`, { method: "POST" }),
  getAnalysisRun: (projectId: string, runId: string) =>
    request<AnalysisRun>(`/projects/${projectId}/analysis-runs/${runId}`),
  cancelAnalysisRun: (projectId: string, runId: string) =>
    request<AnalysisRun>(`/projects/${projectId}/analysis-runs/${runId}/cancel`, { method: "POST" }),
  getDashboard: (projectId: string) => request<DashboardData>(`/projects/${projectId}/dashboard`),
  listDevelopers: (projectId: string) => request<DeveloperSummary[]>(`/projects/${projectId}/developers`),
  getDeveloper: (id: string) => request<DeveloperDetail>(`/developers/${id}`),
  listModules: (projectId: string) => request<ModuleSummary[]>(`/projects/${projectId}/modules`),
  getModule: (id: string) => request<ModuleDetail>(`/modules/${id}`),
  listFiles: (projectId: string, limit = 150) =>
    request<ProjectFile[]>(`/projects/${projectId}/files?limit=${limit}`),
  listLibraries: (projectId: string) => request<LibraryEntry[]>(`/projects/${projectId}/libraries`),
  getKnowledgeGraph: (projectId: string, params?: { developer_id?: string; module_id?: string }) => {
    // Drop unset filters: URLSearchParams would otherwise serialize
    // `undefined` to the literal string "undefined", which the backend
    // (correctly) rejects as an invalid UUID — leaving the page stuck on
    // "No graph data yet" even after a successful analysis.
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
  simulateUnavailability: (projectId: string, developerIds: string[]) =>
    request<SimulationResult>("/simulations/developer-unavailability", {
      method: "POST",
      body: JSON.stringify(
        developerIds.length === 1
          ? { project_id: projectId, developer_id: developerIds[0] }
          : { project_id: projectId, developer_ids: developerIds },
      ),
    }),
  aiQuery: (projectId: string, question: string) =>
    request<AIQueryResponse>("/ai/query", {
      method: "POST",
      body: JSON.stringify({ project_id: projectId, question }),
    }),
};
