import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import PositionsTable from "@/components/investments/PositionsTable";

const MOCK_POSITIONS = [
  {
    account: "TFSA",
    symbol: "ARX",
    name: "ARC Resources Ltd",
    asset_type: "Equity",
    currency: "CAD",
    shares_held: 20,
    avg_cost_per_share: 25,
    cost_basis: 500,
    realized_pl: 0,
    dividends: 5,
  },
  {
    account: "FHSA",
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
    realized_pl: -10,
    dividends: 0,
  },
];

describe("PositionsTable", () => {
  it("renders a row for each position", () => {
    render(<PositionsTable positions={MOCK_POSITIONS} />);

    expect(screen.getByText("ARX")).toBeInTheDocument();
    expect(screen.getByText("VFV")).toBeInTheDocument();
    expect(screen.getByText("ELE")).toBeInTheDocument();
  });

  it("shows account type for each row", () => {
    render(<PositionsTable positions={MOCK_POSITIONS} />);

    expect(screen.getByText("TFSA")).toBeInTheDocument();
    expect(screen.getAllByText("FHSA")).toHaveLength(2);
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

  it("sorts by symbol ascending when Symbol header is clicked once", async () => {
    render(<PositionsTable positions={MOCK_POSITIONS} />);

    await userEvent.click(screen.getByRole("button", { name: /symbol/i }));

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("ARX");
    expect(rows[1]).toHaveTextContent("ELE");
    expect(rows[2]).toHaveTextContent("VFV");
  });

  it("sorts by symbol descending when Symbol header is clicked twice", async () => {
    render(<PositionsTable positions={MOCK_POSITIONS} />);

    await userEvent.click(screen.getByRole("button", { name: /symbol/i }));
    await userEvent.click(screen.getByRole("button", { name: /symbol/i }));

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("VFV");
    expect(rows[1]).toHaveTextContent("ELE");
    expect(rows[2]).toHaveTextContent("ARX");
  });

  it("restores original order when a sorted header is clicked a third time", async () => {
    render(<PositionsTable positions={MOCK_POSITIONS} />);

    await userEvent.click(screen.getByRole("button", { name: /symbol/i }));
    await userEvent.click(screen.getByRole("button", { name: /symbol/i }));
    await userEvent.click(screen.getByRole("button", { name: /symbol/i }));

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("ARX");
    expect(rows[1]).toHaveTextContent("VFV");
    expect(rows[2]).toHaveTextContent("ELE");
  });

  it("sorts by cost basis descending when Cost Basis header is clicked once", async () => {
    render(<PositionsTable positions={MOCK_POSITIONS} />);

    await userEvent.click(screen.getByRole("button", { name: /cost basis/i }));

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("VFV");
    expect(rows[1]).toHaveTextContent("ARX");
    expect(rows[2]).toHaveTextContent("ELE");
  });
});
