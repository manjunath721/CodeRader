/** @type {import('tailwindcss').Config} */
export default {
  content: ["./index.html", "./src/**/*.{js,ts,jsx,tsx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // Risk levels — used consistently across badges, charts, graph nodes (§36)
        risk: {
          low: "#22c55e",
          moderate: "#eab308",
          high: "#f97316",
          critical: "#ef4444",
        },
      },
    },
  },
  plugins: [],
};
