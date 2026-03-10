import math
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

# ============================================================
# Oil & Gas Donut Chart Template
# - 8x8 figures
# - donut width = 0.72
# - startangle = 90
# - white slice borders
# - percentage labels only above threshold
# - simple title + legend layout
# ============================================================


def pct_only(threshold=5):
    def _fmt(pct):
        return f"{pct:.1f}%" if pct >= threshold else ""
    return _fmt


def _legend_handles(colors):
    return [Patch(facecolor=c) for c in colors]


def _safe_show(values, chart_name):
    if not values or sum(v for v in values if v is not None) <= 0:
        raise ValueError(f"{chart_name}: all values are zero or missing.")


def plot_capital_structure(
    company_name,
    market_cap,
    total_debt,
    cash,
    currency="US$",
    equity_color="#90caf9",
    debt_color="#ef5350",
    cash_color="#2e7d32",
):
    """
    Chart 1: Capital Structure
    Breakdown: Market Cap + Net Debt (if positive) OR Net Cash (if negative debt).

    Inputs are expected in millions of currency units.
    """
    net_debt = total_debt - cash

    if net_debt >= 0:
        vals = [market_cap, net_debt]
        colors = [equity_color, debt_color]
        legend_labels = [
            f"Equity: {currency}{market_cap:,.1f}M",
            f"Net Debt: {currency}{net_debt:,.1f}M",
        ]
    else:
        net_cash = abs(net_debt)
        vals = [market_cap, net_cash]
        colors = [equity_color, cash_color]
        legend_labels = [
            f"Equity: {currency}{market_cap:,.1f}M",
            f"Net Cash: {currency}{net_cash:,.1f}M",
        ]

    _safe_show(vals, "Capital Structure")

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(
        vals,
        labels=None,
        autopct=pct_only(5),
        startangle=90,
        colors=colors,
        wedgeprops=dict(width=0.72, edgecolor="white"),
        textprops={"fontsize": 11},
    )

    ax.set_title(f"{company_name} - Capital Structure", fontsize=14)
    ax.legend(
        _legend_handles(colors),
        legend_labels,
        fontsize=14,
        markerscale=1.5,
    )
    plt.tight_layout()
    plt.show()



def plot_nav_vs_ev(
    company_name,
    nav_or_npv,
    enterprise_value,
    nav_label="NAV",
    currency="US$",
    nav_color="#90caf9",
    ev_color="#ef5350",
):
    """
    Chart 2: NAV vs Enterprise Value
    Use only when a credible company-disclosed NAV or study NPV exists.
    Inputs are expected in millions.
    """
    vals = [nav_or_npv, enterprise_value]
    colors = [nav_color, ev_color]

    _safe_show(vals, "NAV vs Enterprise Value")

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(
        vals,
        labels=None,
        autopct=pct_only(7),
        startangle=90,
        colors=colors,
        wedgeprops=dict(width=0.72, edgecolor="white"),
        textprops={"fontsize": 11},
    )

    ax.set_title(f"{company_name} - NAV vs Enterprise Value", fontsize=14)
    legend_labels = [
        f"{nav_label}: {currency}{nav_or_npv:,.1f}M",
        f"Enterprise Value: {currency}{enterprise_value:,.1f}M",
    ]
    ax.legend(
        _legend_handles(colors),
        legend_labels,
        bbox_to_anchor=(1.0, 0.5),
        loc="center left",
    )
    plt.tight_layout()
    plt.show()



def plot_revenue_by_asset(
    company_name,
    period_label,
    revenue_by_asset,
    currency="US$",
    colors=None,
):
    """
    Chart 3: Revenue by Mine / Field / Asset
    Use only when official filings disclose asset-level revenue.
    Inputs should be a dict: {asset_name: revenue_in_millions}
    """
    if not revenue_by_asset:
        raise ValueError("Revenue by asset chart requires a non-empty revenue_by_asset dict.")

    labels = list(revenue_by_asset.keys())
    values = list(revenue_by_asset.values())

    _safe_show(values, "Revenue by Asset")

    if colors is None:
        default_palette = [
            "#4e79a7", "#59a14f", "#f28e2b", "#e15759",
            "#76b7b2", "#edc948", "#b07aa1", "#ff9da7",
        ]
        colors = default_palette[: len(values)]

    fig, ax = plt.subplots(figsize=(8, 8))
    ax.pie(
        values,
        labels=None,
        colors=colors,
        startangle=90,
        autopct=pct_only(5),
        wedgeprops=dict(width=0.72, edgecolor="white"),
        textprops={"fontsize": 11},
    )

    ax.set_title(f"{company_name} - Revenue by Asset ({period_label})", fontsize=14)
    legend_labels = [
        f"{name}: {currency}{value:,.0f}M" for name, value in revenue_by_asset.items()
    ]
    ax.legend(
        _legend_handles(colors),
        legend_labels,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        frameon=False,
        fontsize=11,
    )
    plt.tight_layout()
    plt.show()


# ============================================================
# Example usage (replace with company-specific data from filings)
# ============================================================
if __name__ == "__main__":
    company_name = "Example Energy Corp."

    # -----------------------------
    # Example Inputs
    # -----------------------------
    market_cap = 2_150.0      # US$M
    total_debt = 1_080.0      # US$M
    cash = 230.0              # US$M
    enterprise_value = market_cap + total_debt - cash  # US$M

    # Use company-disclosed NAV or study NPV only
    nav_or_npv = 3_900.0      # US$M
    nav_label = "Company NAV"

    # Asset-level revenue only if officially disclosed
    revenue_by_asset = {
        "North Field": 740,
        "Central Field": 510,
        "West Hub": 295,
        "Offshore Block": 180,
    }
    period_label = "FY2025"

    # Chart 1
    plot_capital_structure(
        company_name=company_name,
        market_cap=market_cap,
        total_debt=total_debt,
        cash=cash,
        currency="US$",
    )

    # Chart 2
    plot_nav_vs_ev(
        company_name=company_name,
        nav_or_npv=nav_or_npv,
        enterprise_value=enterprise_value,
        nav_label=nav_label,
        currency="US$",
    )

    # Chart 3
    plot_revenue_by_asset(
        company_name=company_name,
        period_label=period_label,
        revenue_by_asset=revenue_by_asset,
        currency="US$",
    )
