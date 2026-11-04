export default [
  {
    ignores: ["dist/**", "node_modules/**", "**/*.d.ts", "**/*.ts", "**/*.tsx"],
  },
  {
    files: ["**/*.{js,mjs,cjs}"],
    rules: {
      "no-unused-vars": "warn",
    },
  },
];
