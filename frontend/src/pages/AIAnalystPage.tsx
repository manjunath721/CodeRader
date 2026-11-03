import { useState } from "react";
import { useParams } from "react-router-dom";
import { api } from "@/services/api";
import { Send } from "lucide-react";

const SUGGESTIONS = [
  "Why is Payment high risk?",
  "What are the top risks?",
  "How has resilience changed?",
];

interface Message {
  role: "user" | "assistant";
  text: string;
}

export default function AIAnalystPage() {
  const { projectId } = useParams<{ projectId: string }>();
  const [messages, setMessages] = useState<Message[]>([]);
  const [question, setQuestion] = useState("");
  const [sending, setSending] = useState(false);

  async function send(q: string) {
    if (!projectId || !q.trim()) return;
    setMessages((prev) => [...prev, { role: "user", text: q }]);
    setQuestion("");
    setSending(true);
    try {
      const res = await api.aiQuery(projectId, q);
      setMessages((prev) => [...prev, { role: "assistant", text: res.answer }]);
    } catch (err) {
      setMessages((prev) => [...prev, { role: "assistant", text: `Error: ${String(err)}` }]);
    } finally {
      setSending(false);
    }
  }

  return (
    <div className="flex flex-col h-[calc(100vh-4rem)] max-w-2xl">
      <h1 className="text-xl font-semibold mb-1">AI Project Analyst</h1>
      <p className="text-sm text-slate-500 mb-4">
        Answers are grounded in your project's computed metrics — never invented statistics.
      </p>

      <div className="flex-1 overflow-y-auto space-y-3 mb-4">
        {messages.length === 0 && (
          <div className="flex flex-wrap gap-2">
            {SUGGESTIONS.map((s) => (
              <button
                key={s}
                onClick={() => send(s)}
                className="rounded-full border border-slate-300 px-3 py-1.5 text-xs text-slate-600 hover:border-slate-500 dark:border-slate-700 dark:text-slate-300"
              >
                {s}
              </button>
            ))}
          </div>
        )}
        {messages.map((m, i) => (
          <div
            key={i}
            className={`rounded-xl px-4 py-2.5 text-sm max-w-[85%] ${
              m.role === "user"
                ? "ml-auto bg-slate-900 text-white dark:bg-white dark:text-slate-900"
                : "bg-white border border-slate-200 shadow-sm dark:bg-slate-900 dark:border-slate-800 dark:shadow-none"
            }`}
          >
            {m.text}
          </div>
        ))}
        {sending && <div className="text-xs text-slate-500">Thinking…</div>}
      </div>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          send(question);
        }}
        className="flex gap-2"
      >
        <input
          className="flex-1 rounded-lg bg-white border border-slate-200 px-3 py-2 text-sm outline-none focus:border-indigo-400 focus:ring-2 focus:ring-indigo-500/20 dark:bg-slate-900 dark:border-slate-800 dark:focus:border-slate-600 dark:focus:ring-0"
          placeholder="Ask about risk, resilience, or backup candidates…"
          value={question}
          onChange={(e) => setQuestion(e.target.value)}
        />
        <button
          type="submit"
          disabled={sending || !question.trim()}
          className="rounded-lg bg-slate-900 text-white px-4 py-2 text-sm font-medium hover:bg-slate-700 disabled:opacity-50 dark:bg-white dark:text-slate-900 dark:hover:bg-slate-200"
        >
          <Send size={16} />
        </button>
      </form>
    </div>
  );
}
