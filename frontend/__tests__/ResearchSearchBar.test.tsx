import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import ResearchSearchBar from "@/components/research/ResearchSearchBar";

const MOCK_RESULTS = [
  { ticker: "AAPL", name: "Apple Inc.", cik: "0000320193" },
  { ticker: "AMZN", name: "Amazon.com Inc.", cik: "0001018724" },
  { ticker: "TSLA", name: "Tesla Inc.", cik: "0001318605" },
];

const onSelect = jest.fn();

beforeEach(() => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => MOCK_RESULTS,
  }) as jest.Mock;
});

afterEach(() => {
  jest.clearAllMocks();
});

describe("ResearchSearchBar", () => {
  it("renders the search input", () => {
    render(<ResearchSearchBar onSelect={onSelect} />);

    expect(
      screen.getByPlaceholderText("Search ticker or company name..."),
    ).toBeInTheDocument();
  });

  it("shows dropdown results after typing", async () => {
    render(<ResearchSearchBar onSelect={onSelect} />);

    await userEvent.type(
      screen.getByPlaceholderText("Search ticker or company name..."),
      "A",
    );

    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
      expect(screen.getByText("AMZN")).toBeInTheDocument();
    });
  });

  it("calls onSelect with ticker and name when a result is clicked", async () => {
    render(<ResearchSearchBar onSelect={onSelect} />);

    await userEvent.type(
      screen.getByPlaceholderText("Search ticker or company name..."),
      "A",
    );

    await waitFor(() => screen.getByText("AAPL"));

    await userEvent.click(screen.getByText("AAPL").closest("button")!);

    expect(onSelect).toHaveBeenCalledWith("AAPL", "Apple Inc.");
  });

  it("clears the input after a result is selected", async () => {
    render(<ResearchSearchBar onSelect={onSelect} />);
    const input = screen.getByPlaceholderText(
      "Search ticker or company name...",
    );

    await userEvent.type(input, "A");
    await waitFor(() => screen.getByText("AAPL"));
    await userEvent.click(screen.getByText("AAPL").closest("button")!);

    expect(input).toHaveValue("");
  });

  it("closes dropdown after a result is selected", async () => {
    render(<ResearchSearchBar onSelect={onSelect} />);

    await userEvent.type(
      screen.getByPlaceholderText("Search ticker or company name..."),
      "A",
    );

    await waitFor(() => screen.getByText("AAPL"));
    await userEvent.click(screen.getByText("AAPL").closest("button")!);

    expect(screen.queryByText("AAPL")).not.toBeInTheDocument();
  });

  it("does not show dropdown when input is empty", () => {
    render(<ResearchSearchBar onSelect={onSelect} />);

    expect(screen.queryByRole("listbox")).not.toBeInTheDocument();
  });

  it("shows a scrollable list when results exceed 5", async () => {
    const manyResults = Array.from({ length: 8 }, (_, i) => ({
      ticker: `T${i}`,
      name: `Company ${i}`,
      cik: String(i).padStart(10, "0"),
    }));

    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: true,
      json: async () => manyResults,
    });

    render(<ResearchSearchBar onSelect={onSelect} />);

    await userEvent.type(
      screen.getByPlaceholderText("Search ticker or company name..."),
      "T",
    );

    await waitFor(() => screen.getByText("T0"));

    const list = screen.getByRole("listbox");
    expect(list).toHaveClass("overflow-y-auto");
  });
});
