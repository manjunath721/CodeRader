import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { useAuth } from "@/context/AuthContext";
import { Lock, Mail, ShieldAlert, User as UserIcon } from "lucide-react";

export default function RegisterPage() {
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [fullName, setFullName] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const { register } = useAuth();
  const navigate = useNavigate();

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);
    if (password.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    setLoading(true);
    try {
      await register(email, password, fullName);
      navigate("/");
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : "Registration failed.");
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="min-h-screen flex items-center justify-center bg-slate-50 p-4 dark:bg-slate-950">
      <div className="w-full max-w-md bg-white border border-slate-200 rounded-xl p-8 shadow-sm dark:bg-slate-900 dark:border-slate-800">
        <div className="mb-6 text-center">
          <div className="text-2xl font-bold tracking-tight text-slate-900 dark:text-white">Create Account</div>
          <p className="text-sm text-slate-500 mt-1">Join CodeRadar to analyze engineering resilience</p>
        </div>

        {error && (
          <div className="mb-4 flex items-center gap-2 rounded-lg bg-red-50 p-3 text-sm text-red-700 dark:bg-red-950/50 dark:text-red-300">
            <ShieldAlert size={16} />
            <span>{error}</span>
          </div>
        )}

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">Full Name</label>
            <div className="relative">
              <UserIcon className="absolute left-3 top-2.5 text-slate-400" size={16} />
              <input
                type="text"
                value={fullName}
                onChange={(e) => setFullName(e.target.value)}
                className="w-full rounded-lg border border-slate-300 pl-9 pr-3 py-2 text-sm outline-none focus:border-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:focus:border-slate-500"
                placeholder="Jane Architect"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">Email Address</label>
            <div className="relative">
              <Mail className="absolute left-3 top-2.5 text-slate-400" size={16} />
              <input
                type="email"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                className="w-full rounded-lg border border-slate-300 pl-9 pr-3 py-2 text-sm outline-none focus:border-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:focus:border-slate-500"
                placeholder="developer@example.com"
              />
            </div>
          </div>

          <div>
            <label className="block text-xs font-medium text-slate-700 dark:text-slate-300 mb-1">Password</label>
            <div className="relative">
              <Lock className="absolute left-3 top-2.5 text-slate-400" size={16} />
              <input
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
                className="w-full rounded-lg border border-slate-300 pl-9 pr-3 py-2 text-sm outline-none focus:border-slate-900 dark:border-slate-700 dark:bg-slate-900 dark:text-white dark:focus:border-slate-500"
                placeholder="Min 8 characters"
              />
            </div>
          </div>

          <button
            type="submit"
            disabled={loading}
            className="w-full rounded-lg bg-slate-900 py-2.5 text-sm font-medium text-white hover:bg-slate-800 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-100"
          >
            {loading ? "Creating account…" : "Register"}
          </button>
        </form>

        <div className="mt-6 text-center text-xs text-slate-500">
          Already have an account?{" "}
          <Link to="/login" className="font-medium text-slate-900 hover:underline dark:text-white">
            Sign In
          </Link>
        </div>
      </div>
    </div>
  );
}
