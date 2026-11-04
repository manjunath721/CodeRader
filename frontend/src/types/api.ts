export interface Project {
  id: string;
  name: string;
  description: string | null;
  is_demo: boolean;
  risk_config?: Record<string, unknown>;
  rescan_interval_hours?: number;
  created_at: string;
}

export interface IngestionProgress {
  developers: number;
  modules: number;
  files_total: number;
  files_analyzed: number;
  files_cached: number;
  files_skipped_unreadable: number;
  commits_fetched: number;
  commits_inserted: number;
  commits_already_present: number;
  dependency_edges: number;
  incremental: boolean;
}

export interface AnalysisRun {
  id: string;
  project_id: string;
  status: "pending" | "running" | "complete" | "failed" | "cancelled";
  stage_status: Record<string, string>;
  progress: { ingestion?: Record<string, IngestionProgress> };
  scan_mode: "quick" | "full";
  rescan_type?: string;
  commit_sha?: string | null;
  cancel_requested: boolean;
  started_at: string | null;
  completed_at: string | null;
  error_message: string | null;
}

export interface ModuleSummary {
  id: string;
  name: string;
  path_prefix?: string;
  risk_score: number | null;
  risk_level: string | null;
  bus_factor: number | null;
  concentration_pct: number | null;
  is_critical_knowledge_area: boolean;
}

export interface DashboardData {
  project_id: string;
  project_name: string;
  is_demo: boolean;
  resilience_score: number | null;
  resilience_label: string | null;
  risk_distribution: { LOW: number; MODERATE: number; HIGH: number; CRITICAL: number };
  top_risk_modules: ModuleSummary[];
  critical_knowledge_areas: ModuleSummary[];
  developer_count: number;
  module_count: number;
  last_analysis_run_id: string | null;
  last_analyzed_at: string | null;
}

export interface DeveloperSummary {
  id: string;
  display_name: string;
  primary_email?: string | null;
  modules_count?: number;
  critical_ownership_count?: number;
  single_owner_modules_count?: number;
}

export interface DeveloperDetail {
  id: string;
  display_name: string;
  primary_email: string | null;
  modules: { module_id: string; module_name: string; score: number }[];
  critical_ownership_count: number;
  single_owner_modules_count: number;
  dependency_risk: "LOW" | "MODERATE" | "HIGH";
}

export interface ModuleDetail {
  id: string;
  name: string;
  path_prefix: string;
  risk_score: number | null;
  risk_level: string | null;
  risk_factors: {
    values: Record<string, number>;
    weights: Record<string, number>;
    raw: Record<string, number>;
  } | null;
  bus_factor: number | null;
  concentration_pct: number | null;
  documentation_score: number;
  complexity_avg: number;
  change_frequency_90d: number;
  is_critical_knowledge_area: boolean;
  knowledge_distribution: { developer_id: string; developer_name: string; score: number }[];
  backup_candidates: { developer_id: string; developer_name: string; compatibility: number; reason: string }[];
  dependencies: string[];
  dependents: string[];
}

export interface RiskEntry {
  module_id: string;
  module_name: string;
  score: number;
  level: string;
  factors: ModuleDetail["risk_factors"];
  bus_factor: number;
  concentration_pct: number;
  criticality_score: number;
  is_critical_knowledge_area: boolean;
}

export interface Recommendation {
  id: string;
  severity: "CRITICAL" | "HIGH" | "MODERATE" | "LOW";
  title: string;
  description: string;
  module_id: string | null;
  related_developer_id?: string | null;
  rule_type?: string;
  suggested_action?: string;
  triggering_metric?: string;
}

export interface KnowledgeTransferPlan {
  module: string;
  topics: string[];
  recommended_backup_developer_id: string | null;
  priority: string;
  suggested_format: string;
}

export interface GraphNode {
  id: string;
  type: "Developer" | "Module";
  label: string;
}

export interface ProjectFile {
  id: string;
  path: string;
  name: string;
  language: string | null;
  size_bytes: number;
  complexity: number;
  doc_coverage_pct: number;
  is_test: boolean;
  is_config: boolean;
  module_id: string | null;
  module_name: string | null;
}

export interface LibraryEntry {
  name: string;
  file_count: number;
  used_by_modules: string[];
}

export interface GraphEdge {
  source: string;
  target: string;
  relation: string;
  weight: number;
}

export interface KnowledgeGraphData {
  nodes: GraphNode[];
  edges: GraphEdge[];
}

export interface SimulationResult {
  simulation_id: string;
  resilience_before: number;
  resilience_after: number;
  resilience_label_before: string;
  resilience_label_after: string;
  knowledge_impact_pct: number;
  affected_modules: { id: string; name: string }[];
  backup_candidates: Record<
    string,
    { developer_id: string; developer_name: string; compatibility: number; reason: string }[]
  >;
  risk_propagation: Record<string, Record<string, number>>;
}

export interface User {
  id: string;
  email: string;
  full_name: string;
  role: string;
  is_active: boolean;
  created_at: string;
}

export interface Token {
  access_token: string;
  token_type: string;
  user: User;
}

export interface ProjectMember {
  id: string;
  project_id: string;
  user_id: string;
  role: "owner" | "analyst" | "viewer";
  email?: string;
  full_name?: string;
  created_at: string;
}

export interface AuditLog {
  id: string;
  actor_id: string | null;
  actor_email: string | null;
  action: string;
  resource_type: string;
  resource_id: string | null;
  details: Record<string, unknown>;
  ip_address: string | null;
  created_at: string;
}

export interface ModuleRiskDelta {
  module_id: string;
  name: string;
  old_score: number | null;
  new_score: number | null;
  delta: number;
  old_level: string | null;
  new_level: string | null;
}

export interface AnalysisComparison {
  base_run_id: string;
  target_run_id: string;
  base_commit_sha: string | null;
  target_commit_sha: string | null;
  resilience_before: number | null;
  resilience_after: number | null;
  resilience_delta: number;
  label_before: string | null;
  label_after: string | null;
  modules_added: string[];
  modules_removed: string[];
  risk_changes: ModuleRiskDelta[];
  newly_introduced_risks: string[];
  resolved_risks: string[];
}
