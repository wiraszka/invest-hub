# ------------------------------------------------------------------------
# Donut Chart Template
#
# Standard chart styling:
# - Figure size: 8 x 8
# - Donut width: 0.72
# - Start angle: 90
# - Slice borders: white
# - Percentage labels: show only above threshold
# - Layout: simple title with legend aligned to the right
#
# Default color palette:
# - "#4e79a7"
# - "#59a14f"
# - "#f28e2b"
# - "#e15759"
# - "#76b7b2"
# - "#edc948"
# - "#b07aa1"
# - "#ff9da7"
#
# Capital structure color scheme:
# - Equity: "#90caf9"
# - Debt: "#ef5350"
# - Cash: "#2e7d32"
#
# Oil & gas color scheme:
# - Natural Gas: "#1f4e79"
# - Condensate: "#f39c12"
# - Light Crude Oil: "#2b2b2b"
# - Heavy Crude: "#5c3a21"
# - LNG: "#4a90e2"
# - NGLs: "#16a085"
#
# Commodity color scheme:
# Use an intuitive fallback color if a relevant commodity is not listed.
# - Gold: "#d4af37"
# - Silver: "#ececec"
# - Copper: "#b87333"
# - Zinc: "#7f7f7f"
# - Lead: "#4f4f4f"
# - Nickel: "#7f8c8d"
# - Iron: "#8b0000"
# - Cobalt: "#0047ab"
# - Lithium: "#ff3366"
# - Phosphate: "#ffcc00"
# ------------------------------------------------------------------------

import matplotlib.pyplot as plt
from matplotlib.patches import Patch

DEFAULT_PALETTE = [
    "#4e79a7", "#59a14f", "#f28e2b", "#e15759",
    "#76b7b2", "#edc948", "#b07aa1", "#ff9da7",
]


# ── Shared helpers ─────────────────────────────────────────────────────────────

def pct_only(threshold=5):
    """Return a pie-chart autopct formatter that suppresses labels below threshold."""
    def _fmt(pct):
        return f"{pct:.1f}%" if pct >= threshold else ""
    return _fmt


def _legend_handles(colors):
    return [Patch(facecolor=c) for c in colors]


def _safe_show(values, chart_name):
    if not values or sum(v for v in values if v is not None) <= 0:
        raise ValueError(f"{chart_name}: all values are zero or missing.")


# ── Chart 1: Capital Structure ─────────────────────────────────────────────────

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
    Render a donut chart showing capital structure.

    The chart compares:
    - Equity and Net Debt, if debt exceeds cash
    - Equity and Net Cash, if cash exceeds debt

    Expected inputs are in millions.

    Usage rules for the upstream LLM:
    - Confirm market cap, debt, and cash are available from credible sources.
    - Use inputs from a consistent date or reporting period.
    - Avoid using this chart when capital structure inputs are incomplete,
      stale, or not directly supported by company disclosure.
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
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=11,
    )
    plt.tight_layout()
    plt.show()


# ── Chart 2: NAV vs Enterprise Value ──────────────────────────────────────────

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
    Render a donut chart comparing disclosed NAV / NPV against Enterprise Value.

    Expected inputs are in millions.

    Usage rules for the upstream LLM:
    - Confirm the NAV / NPV figure exists in a credible official source.
    - Choose the correct nav_label based on the disclosed metric.
    - Ensure EV is calculated from a compatible reporting date.
    - Avoid using this chart when the valuation figure is inferred,
      estimated, outdated, or unsupported by disclosure.
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
        fontsize=11,
    )
    plt.tight_layout()
    plt.show()


# ── Chart 3: Revenue by Segment / Geography / Asset ───────────────────────────

def plot_revenue_by_segment(
    company_name,
    period_label,
    revenue_by_segment,
    category_label="Segment",
    currency="US$",
    colors=None,
):
    """
    Render a donut chart for officially disclosed revenue categories.

    Label-selection guidance:
    - Use "Mine" for a multi-asset mining company when revenue is disclosed
      at the mine level.
    - Use "Asset" when the company reports revenue by named assets/fields.
    - Use "Segment" as the default for operating/business segments.

    Expected input:
        {category_name: revenue_in_millions}

    Usage rules for the upstream LLM:
    - Confirm the company officially discloses this revenue breakdown.
    - Select the correct category_label based on the business structure.
    - Supply the latest reported period.
    """
    if not revenue_by_segment:
        raise ValueError("Revenue by segment chart requires a non-empty revenue_by_segment dict.")

    values = list(revenue_by_segment.values())

    _safe_show(values, "Revenue by Segment")

    if colors is None:
        colors = DEFAULT_PALETTE[: len(values)]

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
    ax.set_title(f"{company_name} - Revenue by {category_label} ({period_label})", fontsize=14)
    legend_labels = [
        f"{name}: {currency}{value:,.0f}M" for name, value in revenue_by_segment.items()
    ]
    ax.legend(
        _legend_handles(colors),
        legend_labels,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=11,
    )
    plt.tight_layout()
    plt.show()


# ── Chart 4: Reserves by Asset ─────────────────────────────────────────────────

def plot_pp_reserves_by_asset(
    company_name,
    pp_reserves_by_asset,
    reserve_unit="Moz AuEq",
    colors=None,
):
    """
    Render a donut chart for Proven & Probable Reserves by asset.

    Expected input:
        {asset_name: reserve_amount}

    Usage rules for the upstream LLM:
    - Confirm the company officially discloses asset-level reserve data.
    - Preserve asset names exactly as reported.
    - Use the correct reserve_unit based on the company's disclosure.
    - Avoid using this chart when only total company reserves are
      available and no asset-level breakdown is disclosed.
    """
    if not pp_reserves_by_asset:
        raise ValueError(
            "P&P reserves by asset chart requires a non-empty pp_reserves_by_asset dict."
        )

    values = list(pp_reserves_by_asset.values())

    _safe_show(values, "Proven & Probable Reserves by Asset")

    if colors is None:
        colors = DEFAULT_PALETTE[: len(values)]

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
    ax.set_title(
        f"{company_name} - Proven & Probable Reserves by Asset",
        fontsize=14,
    )
    legend_labels = [
        f"{name}: {value:.1f} {reserve_unit}"
        for name, value in pp_reserves_by_asset.items()
    ]
    ax.legend(
        _legend_handles(colors),
        legend_labels,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=11,
    )
    plt.tight_layout()
    plt.show()


# ── Chart 5: Metal Exposure ────────────────────────────────────────────────────

METAL_COLORS = {
    "Gold": "#d4af37",
    "Silver": "#c0c0c0",
    "Copper": "#b87333",
    "Zinc": "#7f7f7f",
    "Lead": "#4f4f4f",
    "Nickel": "#7f8c8d",
    "Iron": "#8b0000",
    "Cobalt": "#0047ab",
    "Lithium": "#ff3366",
    "Phosphate": "#ffcc00",
}


def plot_metal_exposure(
    company_name,
    period_label,
    metal_exposure,
    exposure_basis="Resources",
    metal_colors=None,
    default_color="#9e9e9e",
):
    """
    Render a donut chart for commodity exposure.

    Expected input:
        {metal_name: exposure_percentage}

    Usage rules for the upstream LLM:
    - Confirm the exposure basis is appropriate for the company.
    - Prefer official company disclosure when available.
    - If derived, ensure the methodology is clear and consistent.
    - Preserve commodity names exactly as used in the selected dataset.
    """
    if not metal_exposure:
        raise ValueError("Metal exposure chart requires a non-empty metal_exposure dict.")

    labels = list(metal_exposure.keys())
    values = list(metal_exposure.values())

    _safe_show(values, "Metal Exposure")

    color_map = metal_colors if metal_colors is not None else METAL_COLORS
    colors = [color_map.get(metal, default_color) for metal in labels]

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
    ax.set_title(
        f"{company_name} - Metal Exposure ({exposure_basis}, {period_label})",
        fontsize=14,
    )
    legend_labels = [f"{metal}: {share:.0f}%" for metal, share in metal_exposure.items()]
    ax.legend(
        _legend_handles(colors),
        legend_labels,
        loc="center left",
        bbox_to_anchor=(1.0, 0.5),
        fontsize=11,
    )
    plt.tight_layout()
    plt.show()


# ── Example usage ──────────────────────────────────────────────────────────────

if __name__ == "__main__":
    # Chart 1: Capital Structure
    plot_capital_structure(
        company_name="Example Corp.",
        market_cap=2_150.0,
        total_debt=1_080.0,
        cash=230.0,
        currency="US$",
    )

    # Chart 2: NAV vs Enterprise Value
    plot_nav_vs_ev(
        company_name="Example Corp.",
        nav_or_npv=3_900.0,
        enterprise_value=2_150.0 + 1_080.0 - 230.0,
        nav_label="Company NAV",
        currency="US$",
    )

    # Chart 3: Revenue by Segment
    plot_revenue_by_segment(
        company_name="Example Gold Corp.",
        period_label="FY2025",
        revenue_by_segment={
            "Greenfield": 740,
            "Silver Tiger": 510,
            "White Rock": 295,
            "Alamos": 180,
        },
        category_label="Mine",
        currency="US$",
    )

    # Chart 4: Reserves by Asset
    plot_pp_reserves_by_asset(
        company_name="Example Metals Corp.",
        pp_reserves_by_asset={
            "Alpha Mine": 2.4,
            "Bravo Project": 1.8,
            "Charlie Mine": 1.1,
            "Delta Deposit": 0.7,
        },
        reserve_unit="Moz AuEq",
    )

    # Chart 5: Metal Exposure
    plot_metal_exposure(
        company_name="Example Metals Corp.",
        period_label="FY2025",
        metal_exposure={
            "Gold": 38,
            "Silver": 24,
            "Copper": 18,
            "Zinc": 12,
            "Lead": 8,
        },
        exposure_basis="Resources",
    )
