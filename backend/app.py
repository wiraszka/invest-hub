from __future__ import annotations

import html
from typing import List

import pandas as pd
import plotly.express as px
import streamlit as st

from constants import (
    COMMODITIES,
    COMMODITY_COLOR_MAP,
    DEFAULT_COMMODITIES,
    MENU_ITEMS,
    TIMEFRAME_OPTIONS,
)
from trends import add_momentum_metrics, fetch_trends, to_long


def inject_sidebar_menu_styles() -> None:
    st.markdown(
        """
<style>
[data-testid="stSidebar"] .sidebar-menu-title {
    font-size: 2rem;
    font-weight: 800;
    letter-spacing: 0.03em;
    margin: 0.25rem 0 0.9rem 0;
}
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label {
    padding-top: 0.15rem;
    padding-bottom: 0.15rem;
}
[data-testid="stSidebar"] .stRadio div[role="radiogroup"] > label p {
    font-size: 1.2rem !important;
    font-weight: 600 !important;
    line-height: 1.15;
}
</style>
        """,
        unsafe_allow_html=True,
    )


def render_interest_panel(latest: pd.DataFrame) -> None:
    st.markdown(
        """
<style>
.interest-panel {
    display: grid;
    grid-template-columns: repeat(auto-fit, minmax(170px, 1fr));
    border-radius: 12px;
    overflow: hidden;
    background: transparent;
    margin-bottom: 0.5rem;
}
.interest-card {
    padding: 0.85rem 1rem;
    min-width: 0;
    text-align: center;
}
.interest-card.with-divider {
    border-right: 1px solid rgba(49, 51, 63, 0.26);
}
.interest-name {
    font-size: 1.28rem;
    font-weight: 700;
    line-height: 1.15;
    margin-bottom: 0.4rem;
    color: #b8beca;
}
.interest-row {
    display: flex;
    align-items: baseline;
    justify-content: center;
    gap: 0.5rem;
    white-space: nowrap;
}
.interest-value {
    font-size: 1.55rem;
    font-weight: 700;
    line-height: 1;
    color: #c9cfda;
}
.interest-delta {
    font-size: 0.95rem;
    font-weight: 600;
    line-height: 1;
}
.interest-delta.positive { color: #16a34a; }
.interest-delta.negative { color: #dc2626; }
.interest-delta.neutral { color: #6b7280; }
@media (max-width: 800px) {
    .interest-panel {
        grid-template-columns: 1fr;
    }
    .interest-card.with-divider {
        border-right: none;
        border-bottom: 1px solid rgba(49, 51, 63, 0.26);
    }
    .interest-name { font-size: 1.18rem; }
    .interest-value { font-size: 1.4rem; }
}
</style>
        """,
        unsafe_allow_html=True,
    )

    cards: List[str] = []
    last_index = len(latest) - 1
    for idx, row in enumerate(latest.itertuples(index=False)):
        momentum = row.Momentum
        if pd.isna(momentum):
            delta_text = "0.0"
            delta_class = "neutral"
        else:
            delta_text = f"{momentum:+.1f}"
            delta_class = (
                "positive"
                if momentum > 0
                else "negative"
                if momentum < 0
                else "neutral"
            )

        divider_class = " with-divider" if idx < last_index else ""
        cards.append(
            '<div class="interest-card'
            + divider_class
            + '">'
            + f'<div class="interest-name">{html.escape(str(row.Commodity))}</div>'
            + '<div class="interest-row">'
            + f'<span class="interest-value">{int(row.Interest)}</span>'
            + f'<span class="interest-delta {delta_class}">{delta_text}</span>'
            + "</div></div>"
        )

    panel_html = '<div class="interest-panel">' + "".join(cards) + "</div>"
    st.markdown(panel_html, unsafe_allow_html=True)


def render_home_page() -> None:
    st.title("HOME")
    st.caption("Landing page for your market dashboard workspace.")
    st.info(
        "Home content placeholder. Add portfolio summary, market overview, or quick links here."
    )


def render_investments_page() -> None:
    st.title("INVESTMENTS")
    st.caption("Portfolio and strategy views can live here.")
    st.info(
        "Investments page placeholder. Add positions, watchlists, allocations, or performance widgets here."
    )


def render_commodities_sentiment_page() -> None:
    st.title("Commodities Retail Sentiment Dashboard")

    if "ms_timeframe" not in st.session_state:
        st.session_state.ms_timeframe = list(TIMEFRAME_OPTIONS.keys())[0]
    if "ms_geo" not in st.session_state:
        st.session_state.ms_geo = ""
    if "ms_selected_commodities" not in st.session_state:
        st.session_state.ms_selected_commodities = DEFAULT_COMMODITIES.copy()
    if "ms_applied_timeframe" not in st.session_state:
        st.session_state.ms_applied_timeframe = st.session_state.ms_timeframe
    if "ms_applied_geo" not in st.session_state:
        st.session_state.ms_applied_geo = st.session_state.ms_geo
    if "ms_applied_selected_commodities" not in st.session_state:
        st.session_state.ms_applied_selected_commodities = (
            st.session_state.ms_selected_commodities.copy()
        )

    def apply_commodity_filters() -> None:
        st.session_state.ms_applied_timeframe = st.session_state.ms_timeframe
        st.session_state.ms_applied_geo = st.session_state.ms_geo
        st.session_state.ms_applied_selected_commodities = (
            st.session_state.ms_selected_commodities.copy()
        )

    timeframe_label = st.session_state.ms_applied_timeframe
    geo = st.session_state.ms_applied_geo
    selected_commodities = st.session_state.ms_applied_selected_commodities

    if not selected_commodities:
        st.warning(
            "Select at least one commodity in the filters below, then refresh the chart."
        )
    else:
        keywords = [COMMODITIES[c] for c in selected_commodities]

        with st.spinner("Fetching Google Trends data..."):
            try:
                raw_df = fetch_trends(
                    keywords=keywords,
                    timeframe_label=timeframe_label,
                    geo=geo.strip().upper(),
                )
            except Exception as exc:
                st.error(f"Failed to fetch data from pytrends: {exc}")
                st.info("Try again in a few seconds or change the timeframe/geo.")
                raw_df = pd.DataFrame()

        if not raw_df.empty:
            inverse_map = {v: k for k, v in COMMODITIES.items()}
            raw_df = raw_df.rename(
                columns={c: inverse_map.get(c, c.title()) for c in raw_df.columns}
            )

            long_df = to_long(raw_df)
            enriched_df = add_momentum_metrics(long_df)

            latest = (
                enriched_df.sort_values("Date")
                .groupby("Commodity", as_index=False)
                .tail(1)[["Commodity", "Interest", "Momentum"]]
                .sort_values("Interest", ascending=False)
            )

            st.subheader("Current Interest Levels")
            render_interest_panel(latest)

            fig = px.line(
                enriched_df,
                x="Date",
                y="Interest",
                color="Commodity",
                title="Google Trends Interest Over Time (Commodities)",
                color_discrete_map=COMMODITY_COLOR_MAP,
            )
            fig.update_layout(legend_title_text="Commodity", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No trend data returned for the selected settings.")

    controls_col1, controls_col2, controls_col3, controls_col4 = st.columns(
        [1.3, 1.0, 2.3, 0.9]
    )
    with controls_col1:
        st.selectbox("Time range", list(TIMEFRAME_OPTIONS.keys()), key="ms_timeframe")
    with controls_col2:
        st.text_input("Geo (country code)", key="ms_geo", placeholder="e.g. US")
    with controls_col3:
        st.multiselect(
            "Commodities", list(COMMODITIES.keys()), key="ms_selected_commodities"
        )
    with controls_col4:
        st.write("")
        st.button("Refresh", on_click=apply_commodity_filters, use_container_width=True)

    st.caption(
        "Note: Google Trends values are normalized (0-100) relative to the selected timeframe and comparison set."
    )


def main() -> None:
    st.set_page_config(
        page_title="Commodities Retail Sentiment Dashboard", layout="wide"
    )
    inject_sidebar_menu_styles()

    with st.sidebar:
        st.markdown(
            '<div class="sidebar-menu-title">MENU</div>', unsafe_allow_html=True
        )
        current_page = st.radio(
            "Navigation",
            MENU_ITEMS,
            index=2,
            label_visibility="collapsed",
        )

    if current_page == "HOME":
        render_home_page()
    elif current_page == "INVESTMENTS":
        render_investments_page()
    else:
        render_commodities_sentiment_page()


if __name__ == "__main__":
    main()
