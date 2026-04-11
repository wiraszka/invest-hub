import { render, screen } from "@testing-library/react";
import Sidebar from "@/components/Sidebar";

// Mock Clerk and Next.js hooks
jest.mock("@clerk/nextjs", () => ({
  UserButton: () => <div data-testid="user-button" />,
}));

jest.mock("next/navigation", () => ({
  usePathname: jest.fn(),
}));

import { usePathname } from "next/navigation";

const mockUsePathname = usePathname as jest.Mock<string>;

const NAV_LABELS = [
  "HOME",
  "INVESTMENTS",
  "SHORTLIST",
  "COMMODITIES SENTIMENT",
];

describe("Sidebar", () => {
  it("renders all navigation items", () => {
    mockUsePathname.mockReturnValue("/");

    render(<Sidebar />);

    for (const label of NAV_LABELS) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });

  it("applies active style to the current route", () => {
    mockUsePathname.mockReturnValue("/investments");

    render(<Sidebar />);

    const activeLink = screen.getByText("INVESTMENTS").closest("a");
    const inactiveLink = screen.getByText("HOME").closest("a");

    expect(activeLink?.className).toContain("bg-neutral-800");
    expect(inactiveLink?.className).not.toContain("bg-neutral-800");
  });

  it("renders the user button", () => {
    mockUsePathname.mockReturnValue("/");

    render(<Sidebar />);

    expect(screen.getByTestId("user-button")).toBeInTheDocument();
  });
});
