import { describe, expect, it } from "vitest";
import { render, screen } from "@testing-library/react";
import RiskBadge from "@/components/RiskBadge";

describe("RiskBadge", () => {
  it("renders the risk level text", () => {
    render(<RiskBadge level="CRITICAL" />);
    expect(screen.getByText("CRITICAL")).toBeInTheDocument();
  });

  it("renders a placeholder when level is null", () => {
    render(<RiskBadge level={null} />);
    expect(screen.getByText("—")).toBeInTheDocument();
  });

  it.each(["LOW", "MODERATE", "HIGH", "CRITICAL"])("renders %s without crashing", (level) => {
    render(<RiskBadge level={level} />);
    expect(screen.getByText(level)).toBeInTheDocument();
  });
});
