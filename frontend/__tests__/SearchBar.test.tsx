import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { useRouter } from "next/navigation";
import SearchBar from "@/components/SearchBar";

jest.mock("next/navigation", () => ({
  useRouter: jest.fn(() => ({ push: jest.fn() })),
}));

const MOCK_RESULTS = [
  { ticker: "AAPL", name: "Apple Inc.", cik: "0000320193" },
  { ticker: "AMZN", name: "Amazon.com Inc.", cik: "0001018724" },
];

beforeEach(() => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => MOCK_RESULTS,
  }) as jest.Mock;
});

afterEach(() => {
  jest.clearAllMocks();
});

describe("SearchBar", () => {
  it("renders the input field", () => {
    render(<SearchBar />);

    expect(
      screen.getByPlaceholderText("Search ticker or company..."),
    ).toBeInTheDocument();
  });

  it("shows results after typing", async () => {
    render(<SearchBar />);

    await userEvent.type(
      screen.getByPlaceholderText("Search ticker or company..."),
      "A",
    );

    await waitFor(() => {
      expect(screen.getByText("AAPL")).toBeInTheDocument();
      expect(screen.getByText("AMZN")).toBeInTheDocument();
    });
  });

  it("navigates to company page on selection", async () => {
    const mockPush = jest.fn();
    jest.mocked(useRouter).mockReturnValue({
      push: mockPush,
      back: jest.fn(),
      forward: jest.fn(),
      refresh: jest.fn(),
      replace: jest.fn(),
      prefetch: jest.fn(),
    } as ReturnType<typeof useRouter>);

    render(<SearchBar />);

    await userEvent.type(
      screen.getByPlaceholderText("Search ticker or company..."),
      "A",
    );

    await waitFor(() => screen.getByText("AAPL"));

    await userEvent.click(screen.getByText("AAPL").closest("button")!);

    expect(mockPush).toHaveBeenCalledWith("/company/AAPL");
  });

  it("clears input after selection", async () => {
    render(<SearchBar />);
    const input = screen.getByPlaceholderText("Search ticker or company...");

    await userEvent.type(input, "A");
    await waitFor(() => screen.getByText("AAPL"));
    await userEvent.click(screen.getByText("AAPL").closest("button")!);

    expect(input).toHaveValue("");
  });
});
