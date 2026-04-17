import { render, screen } from "@testing-library/react";
import ResearchPanel from "@/components/research/ResearchPanel";
import type { AnalysisData } from "@/components/research/ResearchPanel";

jest.mock("recharts", () => ({
  ResponsiveContainer: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  BarChart: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  Bar: () => <div />,
  XAxis: () => <div />,
  YAxis: () => <div />,
  Tooltip: () => <div />,
  PieChart: ({ children }: { children: React.ReactNode }) => (
    <div>{children}</div>
  ),
  Pie: () => <div />,
  Cell: () => <div />,
  Legend: () => <div />,
}));

const BASE_DATA: AnalysisData = {
  ticker: "AAPL",
  company_type: "revenue-generating",
  snapshot:
    "- Apple Inc. designs and sells consumer electronics.\n- Core product is the iPhone.",
  chart_data: {
    capital_structure: {
      market_cap_usd: 3_000_000_000_000,
      net_debt_usd: 50_000_000_000,
    },
    revenue_by_segment: null,
    cash_burn: null,
  },
  xbrl_data: {
    cash: 50_000_000_000,
    total_debt: 100_000_000_000,
    revenue: 400_000_000_000,
    net_income: 100_000_000_000,
    operating_cash_flow: 120_000_000_000,
    shares_outstanding: 15_000_000_000,
    net_debt: 50_000_000_000,
  },
  market_cap_usd: 3_000_000_000_000,
  data_integrity: {
    filing_type: "10-K",
    filing_date: "2025-11-01",
    filing_recency: "fresh",
    reporting_currency: "USD",
    xbrl_quality: "full",
    sections_extracted: true,
    company_independence: "independent",
    llm_model: "claude-sonnet-4-6",
    llm_knowledge_cutoff: "August 2025",
    analysis_timestamp: "2026-04-13T00:00:00Z",
  },
  updated_at: "2026-04-13T00:00:00+00:00",
};

describe("ResearchPanel", () => {
  it("renders the ticker and company type", () => {
    render(<ResearchPanel data={BASE_DATA} />);

    expect(screen.getByText("AAPL")).toBeInTheDocument();
    expect(screen.getByText("revenue-generating")).toBeInTheDocument();
  });

  it("renders snapshot bullet points", () => {
    render(<ResearchPanel data={BASE_DATA} />);

    expect(
      screen.getByText("Apple Inc. designs and sells consumer electronics."),
    ).toBeInTheDocument();
    expect(screen.getByText("Core product is the iPhone.")).toBeInTheDocument();
  });

  it("renders the capital structure chart when data is present", () => {
    render(<ResearchPanel data={BASE_DATA} />);

    expect(screen.getByText("Capital Structure")).toBeInTheDocument();
  });

  it("does not render cash burn section for revenue-generating companies", () => {
    render(<ResearchPanel data={BASE_DATA} />);

    expect(screen.queryByText("Cash Burn")).not.toBeInTheDocument();
  });

  it("renders cash burn section for pre-revenue companies", () => {
    const preRevenue: AnalysisData = {
      ...BASE_DATA,
      ticker: "NNE",
      company_type: "pre-revenue",
      chart_data: {
        capital_structure: { market_cap_usd: 866_000_000, net_debt_usd: null },
        revenue_by_segment: null,
        cash_burn: { annual_burn_usd: 19_000_000 },
      },
    };

    render(<ResearchPanel data={preRevenue} />);

    expect(screen.getByText("Cash Burn")).toBeInTheDocument();
  });

  it("renders revenue by segment chart when data is present", () => {
    const withSegments: AnalysisData = {
      ...BASE_DATA,
      chart_data: {
        ...BASE_DATA.chart_data,
        revenue_by_segment: {
          Services: 80_000_000_000,
          iPhone: 200_000_000_000,
        },
      },
    };

    render(<ResearchPanel data={withSegments} />);

    expect(screen.getByText("Revenue by Segment")).toBeInTheDocument();
  });

  it("does not render revenue by segment when data is null", () => {
    render(<ResearchPanel data={BASE_DATA} />);

    expect(screen.queryByText("Revenue by Segment")).not.toBeInTheDocument();
  });

  it("renders key XBRL metrics", () => {
    render(<ResearchPanel data={BASE_DATA} />);

    expect(screen.getByText("Revenue")).toBeInTheDocument();
    expect(screen.getByText("Net Income")).toBeInTheDocument();
  });
});
