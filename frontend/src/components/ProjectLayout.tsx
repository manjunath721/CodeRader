import { NavLink, Outlet, useParams, Link } from "react-router-dom";
import {
  LayoutDashboard,
  Users,
  Boxes,
  Network,
  FlaskConical,
  ListChecks,
  History,
  Settings,
  LogOut,
  LogIn,
} from "lucide-react";
import ThemeToggle from "@/components/ThemeToggle";
import { useAuth } from "@/context/AuthContext";

const NAV_ITEMS = [
  { to: "", label: "Dashboard", icon: LayoutDashboard, end: true },
  { to: "developers", label: "Developers", icon: Users },
  { to: "modules", label: "Modules", icon: Boxes },
  { to: "graph", label: "Knowledge Graph", icon: Network },
  { to: "simulation", label: "Simulation", icon: FlaskConical },
  { to: "recommendations", label: "Recommendations", icon: ListChecks },
  { to: "history", label: "History & Diffs", icon: History },
  { to: "settings", label: "Settings", icon: Settings },
];

export default function ProjectLayout() {
  const { projectId } = useParams();
  const { user, logout } = useAuth();

  return (
    <div className="min-h-screen flex">
      <aside className="w-56 shrink-0 border-r border-slate-200 bg-white p-4 flex flex-col gap-1 dark:border-slate-800 dark:bg-transparent">
        <div className="px-2 pb-4">
          <div className="text-lg font-semibold tracking-tight">CodeRadar</div>
          <div className="text-xs text-slate-500">Knowledge &amp; Risk Analyzer</div>
        </div>
        {NAV_ITEMS.map(({ to, label, icon: Icon, end }) => (
          <NavLink
            key={to}
            to={`/projects/${projectId}/${to}`}
            end={end}
            className={({ isActive }) =>
              `flex items-center gap-2 rounded-lg px-3 py-2 text-sm transition-colors ${
                isActive
                  ? "bg-slate-900 text-white dark:bg-slate-800"
                  : "text-slate-500 hover:bg-slate-100 hover:text-slate-900 dark:text-slate-400 dark:hover:bg-slate-900 dark:hover:text-slate-200"
              }`
            }
          >
            <Icon size={16} />
            {label}
          </NavLink>
        ))}

        <div className="mt-auto px-2 pt-4 space-y-3 border-t border-slate-200 dark:border-slate-800">
          {user ? (
            <div className="space-y-1">
              <div className="text-xs font-medium text-slate-700 dark:text-slate-300 truncate" title={user.email}>
                {user.full_name || user.email}
              </div>
              <div className="flex items-center justify-between text-[11px] text-slate-500">
                <span className="uppercase">{user.role}</span>
                <button
                  onClick={logout}
                  className="hover:text-risk-critical inline-flex items-center gap-1 transition-colors"
                  title="Sign out"
                >
                  <LogOut size={12} /> Sign out
                </button>
              </div>
            </div>
          ) : (
            <div className="text-xs text-slate-500 flex items-center justify-between">
              <span>Not signed in</span>
              <Link to="/login" className="inline-flex items-center gap-1 text-slate-700 hover:text-slate-900 dark:text-slate-300">
                <LogIn size={12} /> Sign in
              </Link>
            </div>
          )}
          <ThemeToggle className="w-full justify-center" />
          <NavLink to="/" className="block text-xs text-slate-500 hover:text-slate-900 dark:hover:text-slate-300">
            &larr; All projects
          </NavLink>
        </div>
      </aside>
      <main className="flex-1 p-8 max-w-6xl">
        <Outlet />
      </main>
    </div>
  );
}
