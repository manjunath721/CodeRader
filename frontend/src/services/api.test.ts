import { afterEach, describe, expect, it, vi } from "vitest";
import { api } from "@/services/api";

describe("api client", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("resolves with parsed JSON on success", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: true,
        json: async () => [{ id: "1", name: "Demo", description: null, is_demo: false, created_at: "2026-01-01" }],
      }),
    );
    const projects = await api.listProjects();
    expect(projects).toHaveLength(1);
    expect(projects[0].name).toBe("Demo");
  });

  it("throws the backend's detail message on a non-ok response", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({
        ok: false,
        statusText: "Not Found",
        json: async () => ({ detail: "Project not found.", code: "PROJECT_NOT_FOUND" }),
      }),
    );
    await expect(api.getProject("missing-id")).rejects.toThrow("Project not found.");
  });

  it("builds the knowledge-graph query string only from provided filters", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ nodes: [], edges: [] }) });
    vi.stubGlobal("fetch", fetchMock);
    await api.getKnowledgeGraph("proj-1", { developer_id: "dev-1" });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toContain("/projects/proj-1/knowledge-graph?developer_id=dev-1");
  });

  it("omits unset knowledge-graph filters instead of sending literal 'undefined'", async () => {
    const fetchMock = vi.fn().mockResolvedValue({ ok: true, json: async () => ({ nodes: [], edges: [] }) });
    vi.stubGlobal("fetch", fetchMock);
    await api.getKnowledgeGraph("proj-1", { developer_id: undefined, module_id: undefined });
    const calledUrl = fetchMock.mock.calls[0][0] as string;
    expect(calledUrl).toBe("/api/projects/proj-1/knowledge-graph");
    expect(calledUrl).not.toContain("undefined");
  });
});
