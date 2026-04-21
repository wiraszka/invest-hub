import { render, screen } from "@testing-library/react";
import PositionsTable from "@/components/investments/PositionsTable";

const MOCK_POSITIONS = [
  {
    account: "TFSA",
    symbol: "VFV",
    name: "Vanguard S&P 500 Index ETF",
    asset_type: "ETF",
    currency: "CAD",
    shares_held: 7,
    avg_cost_per_share: 100,
    cost_basis: 700,
    realized_pl: 30,
    dividends: 0,
  },
  {
    account: "FHSA",
    symbol: "ELE",
    name: "Elemental Royalty Corp.",
    asset_type: "Equity",
    currency: "CAD",
    shares_held: 11,
    avg_cost_per_share: 21.08,
    cost_basis: 231.88,
    realized_pl: 0,
    dividends: 0,
  },
];

describe("PositionsTable", () => {
  it("renders a row for each position", () => {
    render(<PositionsTable positions={MOCK_POSITIONS} />);

    expect(screen.getByText("VFV")).toBeInTheDocument();
    expect(screen.getByText("ELE")).toBeInTheDocument();
  });

  it("shows account type for each row", () => {
    render(<PositionsTable positions={MOCK_POSITIONS} />);

    expect(screen.getByText("TFSA")).toBeInTheDocument();
    expect(screen.getByText("FHSA")).toBeInTheDocument();
  });

  it("shows shares held", () => {
    render(<PositionsTable positions={MOCK_POSITIONS} />);

    expect(screen.getByText("7")).toBeInTheDocument();
  });

  it("renders column headers", () => {
    render(<PositionsTable positions={MOCK_POSITIONS} />);

    expect(screen.getByText("Symbol")).toBeInTheDocument();
    expect(screen.getByText("Shares")).toBeInTheDocument();
    expect(screen.getByText("Cost Basis")).toBeInTheDocument();
  });

  it("renders empty state when no positions", () => {
    render(<PositionsTable positions={[]} />);

    expect(screen.getByText(/no positions/i)).toBeInTheDocument();
  });
});
