import { Moon, Sun } from "lucide-react";
import { useTheme } from "@/theme";

export default function ThemeToggle({ className = "" }: { className?: string }) {
  const { theme, toggle } = useTheme();
  const dark = theme === "dark";
  return (
    <button
      onClick={toggle}
      title={dark ? "Switch to light mode" : "Switch to dark mode"}
      aria-label={dark ? "Switch to light mode" : "Switch to dark mode"}
      className={`inline-flex items-center gap-1.5 rounded-lg border border-slate-300 bg-white px-2.5 py-1.5 text-xs text-slate-600 transition-colors hover:border-slate-400 hover:text-slate-900 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400 dark:hover:border-slate-600 dark:hover:text-slate-200 ${className}`}
    >
      {dark ? <Sun size={14} /> : <Moon size={14} />}
      <span className="hidden sm:inline">{dark ? "Light" : "Dark"}</span>
    </button>
  );
}
