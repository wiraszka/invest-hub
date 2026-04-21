import { render, screen } from "@testing-library/react";
import TransactionsTable from "@/components/investments/TransactionsTable";

const MOCK_TRANSACTIONS = [
  {
    transaction_date: "2025-09-01",
    account_type: "TFSA",
    activity_type: "Trade",
    activity_sub_type: "SELL",
    symbol: "VFV",
    name: "Vanguard S&P 500 Index ETF",
    currency: "CAD",
    quantity: -3,
    unit_price: 110,
    commission: 0,
    net_cash_amount: 330,
  },
  {
    transaction_date: "2025-08-13",
    account_type: "TFSA",
    activity_type: "Trade",
    activity_sub_type: "BUY",
    symbol: "VFV",
    name: "Vanguard S&P 500 Index ETF",
    currency: "CAD",
    quantity: 10,
    unit_price: 100,
    commission: 0,
    net_cash_amount: -1000,
  },
  {
    transaction_date: "2025-09-26",
    account_type: "TFSA",
    activity_type: "Dividend",
    activity_sub_type: "",
    symbol: null,
    name: null,
    currency: "CAD",
    quantity: null,
    unit_price: null,
    commission: 0,
    net_cash_amount: 10,
  },
];

describe("TransactionsTable", () => {
  it("renders a row for each transaction", () => {
    render(<TransactionsTable transactions={MOCK_TRANSACTIONS} />);

    const rows = screen.getAllByRole("row");
    // header row + 3 data rows
    expect(rows).toHaveLength(4);
  });

  it("shows the symbol for trade transactions", () => {
    render(<TransactionsTable transactions={MOCK_TRANSACTIONS} />);

    expect(screen.getAllByText("VFV").length).toBeGreaterThan(0);
  });

  it("shows human-readable type labels", () => {
    render(<TransactionsTable transactions={MOCK_TRANSACTIONS} />);

    expect(screen.getByText("Buy")).toBeInTheDocument();
    expect(screen.getByText("Sell")).toBeInTheDocument();
    expect(screen.getByText("Dividend")).toBeInTheDocument();
  });

  it("renders column headers", () => {
    render(<TransactionsTable transactions={MOCK_TRANSACTIONS} />);

    expect(screen.getByText("Date")).toBeInTheDocument();
    expect(screen.getByText("Type")).toBeInTheDocument();
    expect(screen.getByText("Amount")).toBeInTheDocument();
  });

  it("renders empty state when no transactions", () => {
    render(<TransactionsTable transactions={[]} />);

    expect(screen.getByText(/no transactions/i)).toBeInTheDocument();
  });
});
