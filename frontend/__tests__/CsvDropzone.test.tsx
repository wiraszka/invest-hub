import { render, screen, waitFor } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import CsvDropzone from "@/components/investments/CsvDropzone";

const onUpload = jest.fn();

beforeEach(() => {
  global.fetch = jest.fn().mockResolvedValue({
    ok: true,
    json: async () => ({ count: 42 }),
  }) as jest.Mock;
});

afterEach(() => {
  jest.clearAllMocks();
});

describe("CsvDropzone", () => {
  it("renders the upload prompt", () => {
    render(<CsvDropzone userId="user_123" onUpload={onUpload} />);

    expect(screen.getByText(/re-upload csv/i)).toBeInTheDocument();
  });

  it("calls fetch and onUpload when a csv file is selected", async () => {
    render(<CsvDropzone userId="user_123" onUpload={onUpload} />);

    const file = new File(["date,amount\n2025-01-01,100"], "activities.csv", {
      type: "text/csv",
    });
    const input = screen.getByTestId("csv-file-input");

    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(global.fetch).toHaveBeenCalledTimes(1);
      expect(onUpload).toHaveBeenCalledTimes(1);
    });
  });

  it("shows an error when the upload fails", async () => {
    (global.fetch as jest.Mock).mockResolvedValueOnce({
      ok: false,
      json: async () => ({ detail: "Bad file" }),
    } as Response);

    render(<CsvDropzone userId="user_123" onUpload={onUpload} />);

    const file = new File(["bad"], "activities.csv", { type: "text/csv" });
    const input = screen.getByTestId("csv-file-input");

    await userEvent.upload(input, file);

    await waitFor(() => {
      expect(screen.getByText(/bad file/i)).toBeInTheDocument();
    });
  });
});
