import { describe, expect, it, vi, afterEach } from "vitest";
import { render, screen, waitFor } from "@testing-library/react";
import App from "@/App";

describe("App routing", () => {
  afterEach(() => {
    vi.unstubAllGlobals();
  });

  it("renders the home page with the project list at /", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: true, json: async () => [] }),
    );
    window.history.pushState({}, "", "/");
    render(<App />);
    expect(await screen.findByText("CodeRadar")).toBeInTheDocument();
    await waitFor(() => expect(screen.getByText(/No projects yet/i)).toBeInTheDocument());
  });
});
