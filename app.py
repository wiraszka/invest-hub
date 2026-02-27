from __future__ import annotations

import html
from typing import Dict, List

import pandas as pd
import plotly.express as px
import streamlit as st
from pytrends.request import TrendReq


COMMODITIES: Dict[str, str] = {
    "Gold": "gold",
    "Silver": "silver",
    "Platinum": "platinum",
    "Copper": "copper",
    "Uranium": "uranium",
}

TIMEFRAME_OPTIONS = {
    "Past 1 week": "now 7-d",
    "Past 1 month": "today 1-m",
    "Past 3 months": "today 3-m",
    "Past 6 months": "custom-6m",
    "Past 12 months": "today 12-m",
    "Past 5 years": "today 5-y",
    "2004 to present": "all",
}

MENU_ITEMS = ["HOME", "INVESTMENTS", "COMMODITIES SENTIMENT"]


def resolve_timeframe(timeframe_label: str) -> str:
    if timeframe_label == "Past 6 months":
        end_date = pd.Timestamp.today().normalize()
        start_date = end_date - pd.Timedelta(days=182)
        return f"{start_date.strftime('%Y-%m-%d')} {end_date.strftime('%Y-%m-%d')}"
    return TIMEFRAME_OPTIONS[timeframe_label]


@st.cache_data(ttl=60 * 30, show_spinner=False)
def fetch_trends(
    keywords: List[str],
    timeframe_label: str,
    geo: str,
    tz_minutes: int = 360,
) -> pd.DataFrame:
    pytrends = TrendReq(hl="en-US", tz=tz_minutes)
    timeframe = resolve_timeframe(timeframe_label)

    pytrends.build_payload(keywords, timeframe=timeframe, geo=geo)
    data = pytrends.interest_over_time()

    if data.empty:
        return data

    if "isPartial" in data.columns:
        data = data.drop(columns=["isPartial"])

    data.index = pd.to_datetime(data.index)
    return data.sort_index()


def to_long(df: pd.DataFrame) -> pd.DataFrame:
    long_df = df.reset_index().rename(columns={"date": "Date"})
    if "Date" not in long_df.columns:
        long_df = long_df.rename(columns={long_df.columns[0]: "Date"})

    long_df = long_df.melt(id_vars="Date", var_name="Commodity", value_name="Interest")
    return long_df


def add_momentum_metrics(df_long: pd.DataFrame) -> pd.DataFrame:
    out = df_long.copy()
    out["Smoothed Interest"] = (
        out.sort_values("Date")
        .groupby("Commodity")["Interest"]
        .transform(lambda s: s.rolling(window=7, min_periods=1).mean())
    )
    out["Momentum"] = out.groupby("Commodity")["Smoothed Interest"].transform(lambda s: s.diff())
    return out


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
            delta_class = "positive" if momentum > 0 else "negative" if momentum < 0 else "neutral"

        divider_class = " with-divider" if idx < last_index else ""
        cards.append(
            "<div class=\"interest-card" + divider_class + "\">"
            + f"<div class=\"interest-name\">{html.escape(str(row.Commodity))}</div>"
            + "<div class=\"interest-row\">"
            + f"<span class=\"interest-value\">{int(row.Interest)}</span>"
            + f"<span class=\"interest-delta {delta_class}\">{delta_text}</span>"
            + "</div></div>"
        )

    panel_html = '<div class="interest-panel">' + "".join(cards) + "</div>"
    st.markdown(panel_html, unsafe_allow_html=True)


def render_home_page() -> None:
    st.title("HOME")
    st.caption("Landing page for your market dashboard workspace.")
    st.info("Home content placeholder. Add portfolio summary, market overview, or quick links here.")


def render_investments_page() -> None:
    st.title("INVESTMENTS")
    st.caption("Portfolio and strategy views can live here.")
    st.info("Investments page placeholder. Add positions, watchlists, allocations, or performance widgets here.")


def render_commodities_sentiment_page() -> None:
    st.title("Commodities Retail Sentiment Dashboard")
    st.caption(
        "Uses Google Trends search interest (via pytrends) as a retail sentiment proxy for commodities: Gold, Silver, Platinum, Copper, and Uranium."
    )

    if "ms_timeframe" not in st.session_state:
        st.session_state.ms_timeframe = list(TIMEFRAME_OPTIONS.keys())[0]
    if "ms_geo" not in st.session_state:
        st.session_state.ms_geo = ""
    if "ms_selected_commodities" not in st.session_state:
        st.session_state.ms_selected_commodities = list(COMMODITIES.keys())

    timeframe_label = st.session_state.ms_timeframe
    geo = st.session_state.ms_geo
    selected_commodities = st.session_state.ms_selected_commodities

    if not selected_commodities:
        st.warning("Select at least one commodity in the filters below.")
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
            raw_df = raw_df.rename(columns={c: inverse_map.get(c, c.title()) for c in raw_df.columns})

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
            )
            fig.update_layout(legend_title_text="Commodity", hovermode="x unified")
            st.plotly_chart(fig, use_container_width=True)
        else:
            st.warning("No trend data returned for the selected settings.")

    controls_col1, controls_col2, controls_col3 = st.columns([1.3, 1.0, 2.3])
    with controls_col1:
        st.selectbox("Time range", list(TIMEFRAME_OPTIONS.keys()), key="ms_timeframe")
    with controls_col2:
        st.text_input("Geo (country code)", key="ms_geo", placeholder="e.g. US")
    with controls_col3:
        st.multiselect("Commodities", list(COMMODITIES.keys()), key="ms_selected_commodities")

    st.caption("Note: Google Trends values are normalized (0-100) relative to the selected timeframe and comparison set.")


def main() -> None:
    st.set_page_config(page_title="Commodities Retail Sentiment Dashboard", layout="wide")
    inject_sidebar_menu_styles()

    with st.sidebar:
        st.markdown('<div class="sidebar-menu-title">MENU</div>', unsafe_allow_html=True)
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
