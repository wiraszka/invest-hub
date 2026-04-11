from __future__ import annotations

import importlib.util
from pathlib import Path

import pandas as pd

PARSER_PATH = Path(__file__).with_name("ws-statement-parser.py")

OUTPUT_COLUMNS = [
    "Account",
    "Ticker",
    "Exchange",
    "Company/Fund Name",
    "Asset Type",
    "Shares Held",
    "Avg Cost/Share (CAD)",
    "Cost Basis (CAD)",
    "Current Price (CAD)",
    "Market Value (CAD)",
    "Unrealized P/L (CAD)",
    "Unrealized P/L (%)",
    "Realized P/L (CAD)",
    "Dividends/Distributions (CAD)",
    "Total Net P/L (CAD)",
]


def load_statement_parser_module():
    spec = importlib.util.spec_from_file_location("ws_statement_parser", PARSER_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def infer_account(source_file: str) -> str:
    return Path(source_file).name.split("-", 1)[0]


def infer_asset_type(company_name: str | float | None) -> str | pd.NA:
    if pd.isna(company_name):
        return pd.NA

    normalized_name = str(company_name).lower()
    if "etf" in normalized_name:
        return "ETF"
    if "trust" in normalized_name:
        return "Trust"
    if "fund" in normalized_name:
        return "Fund"
    return "Equity"


def prepare_transactions(statement_df: pd.DataFrame) -> pd.DataFrame:
    transactions_df = statement_df.copy()
    transactions_df["Account"] = transactions_df["source_file"].map(infer_account)
    transactions_df["event_date"] = transactions_df["execution_date"].combine_first(transactions_df["date"])
    transactions_df = transactions_df.sort_values(
        ["event_date", "date", "source_file", "transaction", "description"],
        ascending=[True, True, True, True, True],
        kind="stable",
    ).reset_index(drop=True)
    return transactions_df


def initialize_position(row: pd.Series) -> dict:
    return {
        "Account": row["Account"],
        "Ticker": row["ticker"],
        "Exchange": pd.NA,
        "Company/Fund Name": row["company_name"],
        "Asset Type": infer_asset_type(row["company_name"]),
        "Shares Held": 0.0,
        "Avg Cost/Share (CAD)": 0.0,
        "Cost Basis (CAD)": 0.0,
        "Current Price (CAD)": pd.NA,
        "Market Value (CAD)": pd.NA,
        "Unrealized P/L (CAD)": pd.NA,
        "Unrealized P/L (%)": pd.NA,
        "Realized P/L (CAD)": 0.0,
        "Dividends/Distributions (CAD)": 0.0,
        "Total Net P/L (CAD)": pd.NA,
    }


def apply_buy(position: dict, row: pd.Series) -> None:
    shares_bought = float(row["share_count"])
    transaction_cost = abs(float(row["amount"]))
    position["Shares Held"] += shares_bought
    position["Cost Basis (CAD)"] += transaction_cost


def apply_sell(position: dict, row: pd.Series) -> None:
    shares_sold = float(row["share_count"])
    current_shares = float(position["Shares Held"])
    average_cost = 0.0 if current_shares == 0 else float(position["Cost Basis (CAD)"]) / current_shares
    cost_removed = average_cost * shares_sold
    proceeds = float(row["amount"])

    position["Shares Held"] -= shares_sold
    position["Cost Basis (CAD)"] -= cost_removed
    position["Realized P/L (CAD)"] += proceeds - cost_removed


def apply_dividend(position: dict, row: pd.Series) -> None:
    position["Dividends/Distributions (CAD)"] += float(row["amount"])


def apply_stock_distribution(position: dict, row: pd.Series) -> None:
    distributed_shares = float(row["share_count"])
    current_shares = float(position["Shares Held"])

    if distributed_shares >= 0:
        position["Shares Held"] += distributed_shares
        return

    shares_removed = abs(distributed_shares)
    average_cost = 0.0 if current_shares == 0 else float(position["Cost Basis (CAD)"]) / current_shares
    cost_removed = average_cost * shares_removed

    position["Shares Held"] -= shares_removed
    position["Cost Basis (CAD)"] -= cost_removed


def finalize_position(position: dict) -> dict:
    shares_held = float(position["Shares Held"])
    cost_basis = float(position["Cost Basis (CAD)"])

    if abs(shares_held) < 1e-10:
        shares_held = 0.0
    if abs(cost_basis) < 1e-10:
        cost_basis = 0.0

    position["Shares Held"] = shares_held
    position["Cost Basis (CAD)"] = cost_basis
    position["Avg Cost/Share (CAD)"] = cost_basis / shares_held if shares_held else 0.0

    current_price = position["Current Price (CAD)"]
    if pd.notna(current_price):
        market_value = shares_held * float(current_price)
        unrealized_pl = market_value - cost_basis
        unrealized_pl_pct = pd.NA if cost_basis == 0 else unrealized_pl / cost_basis
        total_net_pl = float(position["Realized P/L (CAD)"]) + unrealized_pl + float(position["Dividends/Distributions (CAD)"])
        position["Market Value (CAD)"] = market_value
        position["Unrealized P/L (CAD)"] = unrealized_pl
        position["Unrealized P/L (%)"] = unrealized_pl_pct
        position["Total Net P/L (CAD)"] = total_net_pl
    else:
        position["Market Value (CAD)"] = pd.NA
        position["Unrealized P/L (CAD)"] = pd.NA
        position["Unrealized P/L (%)"] = pd.NA
        position["Total Net P/L (CAD)"] = pd.NA

    return position


def build_portfolio_tracker(statement_df: pd.DataFrame) -> pd.DataFrame:
    transactions_df = prepare_transactions(statement_df)
    positions: dict[tuple[str, str, str], dict] = {}

    for row in transactions_df.itertuples(index=False):
        if pd.isna(row.company_name) or pd.isna(row.ticker):
            continue

        key = (row.Account, row.ticker, row.company_name)
        position = positions.setdefault(key, initialize_position(pd.Series(row._asdict())))

        if row.transaction == "BUY":
            apply_buy(position, pd.Series(row._asdict()))
        elif row.transaction == "SELL":
            apply_sell(position, pd.Series(row._asdict()))
        elif row.transaction == "DIV":
            apply_dividend(position, pd.Series(row._asdict()))
        elif row.transaction == "STKDIS":
            apply_stock_distribution(position, pd.Series(row._asdict()))

    portfolio_rows = [finalize_position(position) for position in positions.values()]
    portfolio_df = pd.DataFrame(portfolio_rows)
    portfolio_df = portfolio_df.sort_values(["Account", "Company/Fund Name"], kind="stable").reset_index(drop=True)
    return portfolio_df[OUTPUT_COLUMNS]


statement_parser = load_statement_parser_module()
transactions_df = statement_parser.df.copy()
portfolio_df = build_portfolio_tracker(transactions_df)
df = portfolio_df


if __name__ == "__main__":
    print(df.to_string(index=False))
