import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
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
    symbol: "ARX",
    name: "ARC Resources Ltd",
    currency: "CAD",
    quantity: 10,
    unit_price: 25,
    commission: 0,
    net_cash_amount: -250,
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
    expect(rows).toHaveLength(4);
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

  it("sorts by date ascending when Date header is clicked once", async () => {
    render(<TransactionsTable transactions={MOCK_TRANSACTIONS} />);

    await userEvent.click(screen.getByRole("button", { name: /date/i }));

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("2025-08-13");
    expect(rows[1]).toHaveTextContent("2025-09-01");
    expect(rows[2]).toHaveTextContent("2025-09-26");
  });

  it("sorts by date descending when Date header is clicked twice", async () => {
    render(<TransactionsTable transactions={MOCK_TRANSACTIONS} />);

    await userEvent.click(screen.getByRole("button", { name: /date/i }));
    await userEvent.click(screen.getByRole("button", { name: /date/i }));

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("2025-09-26");
    expect(rows[1]).toHaveTextContent("2025-09-01");
    expect(rows[2]).toHaveTextContent("2025-08-13");
  });

  it("restores original order when a sorted header is clicked a third time", async () => {
    render(<TransactionsTable transactions={MOCK_TRANSACTIONS} />);

    await userEvent.click(screen.getByRole("button", { name: /date/i }));
    await userEvent.click(screen.getByRole("button", { name: /date/i }));
    await userEvent.click(screen.getByRole("button", { name: /date/i }));

    const rows = screen.getAllByRole("row").slice(1);
    expect(rows[0]).toHaveTextContent("2025-09-01");
    expect(rows[1]).toHaveTextContent("2025-08-13");
    expect(rows[2]).toHaveTextContent("2025-09-26");
  });
});
