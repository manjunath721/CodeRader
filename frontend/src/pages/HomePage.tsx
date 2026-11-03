import { useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { api } from "@/services/api";
import type { Project } from "@/types/api";
import { Plus, FolderGit2, Sparkles, FlaskConical, Trash2 } from "lucide-react";
import ThemeToggle from "@/components/ThemeToggle";

export default function HomePage() {
  const [projects, setProjects] = useState<Project[] | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [name, setName] = useState("");
  const [repoUrl, setRepoUrl] = useState("");
  const [provider, setProvider] = useState("git");
  const [creating, setCreating] = useState(false);
  const [loadingDemo, setLoadingDemo] = useState(false);
  const navigate = useNavigate();

  const load = () => {
    api.listProjects().then(setProjects).catch((e) => setError(String(e)));
  };

  useEffect(load, []);

  async function handleCreate(e: React.FormEvent) {
    e.preventDefault();
    if (!name.trim()) return;
    setCreating(true);
    setError(null);
    try {
      const project = await api.createProject(name.trim());
      if (repoUrl.trim()) {
        await api.addRepository(project.id, repoUrl.trim(), provider);
      }
      navigate(`/projects/${project.id}`);
    } catch (err) {
      setError(String(err));
    } finally {
      setCreating(false);
    }
  }

  async function handleLoadDemo() {
    setLoadingDemo(true);
    setError(null);
    try {
      const demo = await api.ensureDemo();
      navigate(`/projects/${demo.project_id}`);
    } catch (err) {
      setError(String(err));
    } finally {
      setLoadingDemo(false);
    }
  }

  async function handleDelete(p: Project) {
    if (!window.confirm(`Delete project "${p.name}" and all of its analysis data? This cannot be undone.`)) return;
    setError(null);
    try {
      await api.deleteProject(p.id);
      load();
    } catch (err) {
      setError(String(err));
    }
  }

  const demoProjects = projects?.filter((p) => p.is_demo) ?? [];
  const realProjects = projects?.filter((p) => !p.is_demo) ?? [];

  return (
    <div className="max-w-3xl mx-auto px-6 py-12">
      <div className="flex items-start justify-between gap-4">
        <h1 className="text-2xl font-semibold mb-1">CodeRadar</h1>
        <ThemeToggle />
      </div>
      <p className="text-slate-600 dark:text-slate-400 mb-8">
        AI-Powered Software Team Knowledge &amp; Risk Analyzer. Create a project, attach a repository, and run
        analysis to see real risk and resilience metrics.
      </p>

      <div className="rounded-xl border border-indigo-500/30 bg-indigo-500/5 p-5 mb-6 flex flex-wrap items-center gap-4">
        <div className="flex-1 min-w-[220px]">
          <div className="text-sm font-medium text-slate-200 flex items-center gap-1.5">
            <Sparkles size={15} className="text-indigo-400" /> Try the demo workspace
          </div>
          <p className="text-xs text-slate-400 mt-1">
            10 developers, 8 modules, real dependency edges — analyzed end-to-end. Always available in one click.
          </p>
        </div>
        <button
          onClick={handleLoadDemo}
          disabled={loadingDemo}
          className="inline-flex items-center gap-2 rounded-lg bg-indigo-500 text-white px-4 py-2 text-sm font-medium hover:bg-indigo-400 disabled:opacity-50"
        >
          <FlaskConical size={16} />
          {loadingDemo ? "Preparing demo…" : demoProjects.length > 0 ? "Open demo workspace" : "Load demo workspace"}
        </button>
      </div>
      {loadingDemo && (
        <div className="text-xs text-slate-500 -mt-3 mb-6">
          First load builds the synthetic repository and runs full analysis — this can take about a minute.
        </div>
      )}

      <form onSubmit={handleCreate} className="rounded-xl border border-slate-200 bg-white p-5 mb-10 space-y-3 shadow-sm dark:border-slate-800 dark:bg-transparent dark:shadow-none">
        <div className="text-sm font-medium text-slate-700 dark:text-slate-300">New project</div>
        <input
          className="w-full rounded-lg bg-slate-100 border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20 dark:bg-slate-900 dark:border-slate-800 dark:focus:border-slate-600 dark:focus:ring-0"
          placeholder="Project name"
          value={name}
          onChange={(e) => setName(e.target.value)}
        />
        <div className="flex gap-2">
          <input
            className="flex-1 rounded-lg bg-slate-100 border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20 dark:bg-slate-900 dark:border-slate-800 dark:focus:border-slate-600 dark:focus:ring-0"
            placeholder="Repository URL or local path"
            value={repoUrl}
            onChange={(e) => setRepoUrl(e.target.value)} required
          />
          <select
            className="rounded-lg bg-slate-100 border border-slate-200 px-2 py-2 text-sm dark:bg-slate-900 dark:border-slate-800"
            value={provider}
            onChange={(e) => setProvider(e.target.value)}
          >
            {/* <option value="git">git</option> */}
            <option value="github">github</option>
            {/* <option value="local">local</option> */}
          </select>
        </div>
        <button
          type="submit"
          disabled={creating || !name.trim()}
          className="inline-flex items-center gap-2 rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
        >
          <Plus size={16} /> Create project
        </button>
        {error && <div className="text-sm text-risk-critical">{error}</div>}
      </form>

      <div className="flex items-baseline justify-between mb-3">
        <div className="text-sm font-medium text-slate-700 dark:text-slate-300">Your projects</div>
        <div className="text-[11px] text-slate-500">Hover a row and click the trash icon to delete a project</div>
      </div>
      {projects === null && <div className="text-slate-500 text-sm">Loading…</div>}
      {projects?.length === 0 && (
        <div className="text-slate-500 text-sm">No projects yet — load the demo or create one above.</div>
      )}
      <div className="space-y-2">
        {demoProjects.map((p) => (
          <div
            key={p.id}
            className="w-full flex items-center gap-3 rounded-lg border border-indigo-500/40 bg-indigo-500/5 px-4 py-3 hover:border-indigo-400 transition-colors"
          >
            <button onClick={() => navigate(`/projects/${p.id}`)} className="flex flex-1 items-center gap-3 text-left">
              <FlaskConical size={18} className="text-indigo-400 shrink-0" />
              <div className="flex-1">
                <div className="text-sm font-medium">{p.name}</div>
                <div className="text-xs text-slate-500">Demo data (synthetic) — ready to explore</div>
              </div>
              <span className="text-[11px] font-medium uppercase tracking-wide rounded-full bg-indigo-500/20 text-indigo-300 px-2 py-0.5">
                Demo
              </span>
            </button>
            <button
              onClick={() => handleDelete(p)}
              title={`Delete ${p.name}`}
              aria-label={`Delete ${p.name}`}
              className="rounded p-1.5 text-slate-500 hover:bg-slate-200 hover:text-risk-critical dark:hover:bg-slate-800"
            >
              <Trash2 size={15} />
            </button>
          </div>
        ))}
        {realProjects.map((p) => (
          <div
            key={p.id}
            className="w-full flex items-center gap-3 rounded-lg border border-slate-200 bg-white px-4 py-3 shadow-sm hover:border-slate-400 transition-colors dark:border-slate-800 dark:bg-transparent dark:shadow-none dark:hover:border-slate-600"
          >
            <button onClick={() => navigate(`/projects/${p.id}`)} className="flex flex-1 items-center gap-3 text-left">
              <FolderGit2 size={18} className="text-slate-500 shrink-0" />
              <div>
                <div className="text-sm font-medium">{p.name}</div>
              </div>
            </button>
            <button
              onClick={() => handleDelete(p)}
              title={`Delete ${p.name}`}
              aria-label={`Delete ${p.name}`}
              className="rounded p-1.5 text-slate-500 hover:bg-slate-200 hover:text-risk-critical dark:hover:bg-slate-800"
            >
              <Trash2 size={15} />
            </button>
          </div>
        ))}
      </div>
    </div>
  );
}
