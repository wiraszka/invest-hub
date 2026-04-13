import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import RecentChips from "@/components/research/RecentChips";

const onSelect = jest.fn();

afterEach(() => {
  jest.clearAllMocks();
});

describe("RecentChips", () => {
  it("renders nothing when there are no recent tickers", () => {
    const { container } = render(
      <RecentChips tickers={[]} onSelect={onSelect} />,
    );

    expect(container.firstChild).toBeNull();
  });

  it("renders a chip for each ticker", () => {
    render(
      <RecentChips tickers={["AAPL", "TSLA", "NNE"]} onSelect={onSelect} />,
    );

    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("TSLA")).toBeInTheDocument();
    expect(screen.getByText("NNE")).toBeInTheDocument();
  });

  it("calls onSelect with the ticker when a chip is clicked", async () => {
    render(<RecentChips tickers={["AAPL", "TSLA"]} onSelect={onSelect} />);

    await userEvent.click(screen.getByText("TSLA"));

    expect(onSelect).toHaveBeenCalledWith("TSLA");
    expect(onSelect).toHaveBeenCalledTimes(1);
  });

  it("renders tickers in the order provided", () => {
    render(
      <RecentChips tickers={["NNE", "AAPL", "TSLA"]} onSelect={onSelect} />,
    );

    const chips = screen.getAllByRole("button");
    expect(chips[0]).toHaveTextContent("NNE");
    expect(chips[1]).toHaveTextContent("AAPL");
    expect(chips[2]).toHaveTextContent("TSLA");
  });
});
