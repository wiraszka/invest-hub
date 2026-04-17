from pathlib import Path

import pandas as pd

STATEMENTS_DIR = Path("ws-statements")
CSV_PATH = (
    STATEMENTS_DIR / "TFSA-monthly-statement-transactions-HQ8GXMMK0CAD-2025-07-01.csv"
)

BUY_SELL_PATTERN = (
    r"^(?P<ticker>.+?) - "
    r"(?P<company_name>.+?): "
    r"(?P<order_type>Bought|Sold) "
    r"(?P<share_count>\d+(?:\.\d+)?) shares"
    r"(?: at \$(?P<price>\d+(?:\.\d+)?) per share)? "
    r"\(executed at (?P<execution_date>\d{4}-\d{2}-\d{2})\)"
    r"(?:, FX Rate: (?P<fx_rate>\d+(?:\.\d+)?))?$"
)

DIV_PATTERN = (
    r"^(?P<ticker>.+?) - "
    r"(?P<company_name>.+?): "
    r"(?P<dividend_type>Cash dividend distribution), received on "
    r"(?P<div_execution_date>\d{4}-\d{2}-\d{2}), record date of "
    r"\d{4}-\d{2}-\d{2}"
    r"(?:, FX Rate: (?P<fx_rate>\d+(?:\.\d+)?))?$"
)

NRT_PATTERN = (
    r"^(?P<tax_type>Non-resident tax) "
    r"\(executed at (?P<nrt_execution_date>\d{4}-\d{2}-\d{2})\)$"
)

CONT_PATTERN = (
    r"^(?P<contribution_type>Contribution) "
    r"\(executed at (?P<cont_execution_date>\d{4}-\d{2}-\d{2})\)$"
)

FPLINT_PATTERN = (
    r"^(?P<interest_type>Stock lending monthly interest payment)"
    r"(?:, FX Rate: (?P<fplint_fx_rate>\d+(?:\.\d+)?))?$"
)

STKDIS_PATTERN = (
    r"^(?P<ticker>.+?) - "
    r"(?P<company_name>.+?): "
    r"(?P<distribution_type>Distribution of) "
    r"(?P<distribution_share_count>-?\d+(?:\.\d+)?) shares "
    r"\(executed at (?P<stkdis_execution_date>\d{4}-\d{2}-\d{2})\)$"
)

TRFIN_PATTERN = (
    r"^(?P<transfer_type>Money transfer into the account) "
    r"\(executed at (?P<trfin_execution_date>\d{4}-\d{2}-\d{2})\)$"
)

WD_PATTERN = (
    r"^(?P<withdrawal_type>Non-contribution withdrawal) "
    r"\(executed at (?P<wd_execution_date>\d{4}-\d{2}-\d{2})\)$"
)


def _existing_column(statement_df: pd.DataFrame, column_name: str) -> pd.Series:
    if column_name in statement_df.columns:
        return statement_df[column_name]
    return pd.Series(pd.NA, index=statement_df.index, dtype="object")


def load_statement(csv_path: Path = CSV_PATH) -> pd.DataFrame:
    statement_df = pd.read_csv(csv_path)
    statement_df["date"] = pd.to_datetime(statement_df["date"])
    statement_df["amount"] = pd.to_numeric(statement_df["amount"])
    statement_df["balance"] = pd.to_numeric(statement_df["balance"])
    statement_df["source_file"] = Path(csv_path).name
    return statement_df


def load_all_statements(statements_dir: Path = STATEMENTS_DIR) -> pd.DataFrame:
    csv_paths = sorted(statements_dir.glob("*.csv"))
    statement_frames = [load_statement(csv_path) for csv_path in csv_paths]
    return pd.concat(statement_frames, ignore_index=True)


def remove_non_transactions(statement_df: pd.DataFrame) -> pd.DataFrame:
    filtered_df = statement_df[
        ~statement_df["transaction"].isin(["LOAN", "RECALL", "STKREORG"])
    ].reset_index(drop=True)
    return filtered_df


def parse_trade_descriptions(statement_df: pd.DataFrame) -> pd.DataFrame:
    parsed_df = statement_df.copy()
    extracted_fields = (
        parsed_df["description"]
        .where(parsed_df["transaction"].isin(["BUY", "SELL"]))
        .str.extract(BUY_SELL_PATTERN)
    )

    parsed_df["ticker"] = extracted_fields["ticker"].combine_first(
        _existing_column(parsed_df, "ticker")
    )
    parsed_df["company_name"] = extracted_fields["company_name"].combine_first(
        _existing_column(parsed_df, "company_name")
    )
    parsed_df["type"] = extracted_fields["order_type"].combine_first(
        _existing_column(parsed_df, "type")
    )
    parsed_df["share_count"] = pd.to_numeric(extracted_fields["share_count"])
    parsed_df["price"] = pd.to_numeric(extracted_fields["price"])
    parsed_df["execution_date"] = pd.to_datetime(
        extracted_fields["execution_date"]
    ).combine_first(_existing_column(parsed_df, "execution_date"))
    parsed_df["fx_rate"] = pd.to_numeric(extracted_fields["fx_rate"]).combine_first(
        pd.to_numeric(_existing_column(parsed_df, "fx_rate"), errors="coerce")
    )
    return parsed_df


def parse_div_description(statement_df: pd.DataFrame) -> pd.DataFrame:
    parsed_df = statement_df.copy()
    extracted_fields = (
        parsed_df["description"]
        .where(parsed_df["transaction"].eq("DIV"))
        .str.extract(DIV_PATTERN)
    )

    parsed_df["ticker"] = extracted_fields["ticker"].combine_first(
        _existing_column(parsed_df, "ticker")
    )
    parsed_df["company_name"] = extracted_fields["company_name"].combine_first(
        _existing_column(parsed_df, "company_name")
    )
    parsed_df["type"] = extracted_fields["dividend_type"].combine_first(
        _existing_column(parsed_df, "type")
    )
    parsed_df["execution_date"] = pd.to_datetime(
        extracted_fields["div_execution_date"]
    ).combine_first(_existing_column(parsed_df, "execution_date"))
    parsed_df["fx_rate"] = pd.to_numeric(extracted_fields["fx_rate"]).combine_first(
        pd.to_numeric(_existing_column(parsed_df, "fx_rate"), errors="coerce")
    )
    return parsed_df


def parse_nrt_description(statement_df: pd.DataFrame) -> pd.DataFrame:
    parsed_df = statement_df.copy()
    extracted_fields = (
        parsed_df["description"]
        .where(parsed_df["transaction"].eq("NRT"))
        .str.extract(NRT_PATTERN)
    )

    parsed_df["type"] = extracted_fields["tax_type"].combine_first(
        _existing_column(parsed_df, "type")
    )
    parsed_df["execution_date"] = pd.to_datetime(
        extracted_fields["nrt_execution_date"]
    ).combine_first(_existing_column(parsed_df, "execution_date"))
    return parsed_df


def parse_cont_description(statement_df: pd.DataFrame) -> pd.DataFrame:
    parsed_df = statement_df.copy()
    extracted_fields = (
        parsed_df["description"]
        .where(parsed_df["transaction"].eq("CONT"))
        .str.extract(CONT_PATTERN)
    )

    parsed_df["type"] = extracted_fields["contribution_type"].combine_first(
        _existing_column(parsed_df, "type")
    )
    parsed_df["execution_date"] = pd.to_datetime(
        extracted_fields["cont_execution_date"]
    ).combine_first(_existing_column(parsed_df, "execution_date"))
    return parsed_df


def parse_fplint_description(statement_df: pd.DataFrame) -> pd.DataFrame:
    parsed_df = statement_df.copy()
    extracted_fields = (
        parsed_df["description"]
        .where(parsed_df["transaction"].eq("FPLINT"))
        .str.extract(FPLINT_PATTERN)
    )

    parsed_df["type"] = extracted_fields["interest_type"].combine_first(
        _existing_column(parsed_df, "type")
    )
    parsed_df["fx_rate"] = pd.to_numeric(
        extracted_fields["fplint_fx_rate"]
    ).combine_first(
        pd.to_numeric(_existing_column(parsed_df, "fx_rate"), errors="coerce")
    )
    return parsed_df


def parse_stkdis_description(statement_df: pd.DataFrame) -> pd.DataFrame:
    parsed_df = statement_df.copy()
    extracted_fields = (
        parsed_df["description"]
        .where(parsed_df["transaction"].eq("STKDIS"))
        .str.extract(STKDIS_PATTERN)
    )

    parsed_df["ticker"] = extracted_fields["ticker"].combine_first(
        _existing_column(parsed_df, "ticker")
    )
    parsed_df["company_name"] = extracted_fields["company_name"].combine_first(
        _existing_column(parsed_df, "company_name")
    )
    parsed_df["type"] = extracted_fields["distribution_type"].combine_first(
        _existing_column(parsed_df, "type")
    )
    parsed_df["share_count"] = pd.to_numeric(
        extracted_fields["distribution_share_count"]
    ).combine_first(
        pd.to_numeric(_existing_column(parsed_df, "share_count"), errors="coerce")
    )
    parsed_df["execution_date"] = pd.to_datetime(
        extracted_fields["stkdis_execution_date"]
    ).combine_first(_existing_column(parsed_df, "execution_date"))
    return parsed_df


def parse_trfin_description(statement_df: pd.DataFrame) -> pd.DataFrame:
    parsed_df = statement_df.copy()
    extracted_fields = (
        parsed_df["description"]
        .where(parsed_df["transaction"].eq("TRFIN"))
        .str.extract(TRFIN_PATTERN)
    )

    parsed_df["type"] = extracted_fields["transfer_type"].combine_first(
        _existing_column(parsed_df, "type")
    )
    parsed_df["execution_date"] = pd.to_datetime(
        extracted_fields["trfin_execution_date"]
    ).combine_first(_existing_column(parsed_df, "execution_date"))
    return parsed_df


def parse_wd_description(statement_df: pd.DataFrame) -> pd.DataFrame:
    parsed_df = statement_df.copy()
    extracted_fields = (
        parsed_df["description"]
        .where(parsed_df["transaction"].eq("WD"))
        .str.extract(WD_PATTERN)
    )

    parsed_df["type"] = extracted_fields["withdrawal_type"].combine_first(
        _existing_column(parsed_df, "type")
    )
    parsed_df["execution_date"] = pd.to_datetime(
        extracted_fields["wd_execution_date"]
    ).combine_first(_existing_column(parsed_df, "execution_date"))
    return parsed_df


def add_debit_credit_columns(statement_df: pd.DataFrame) -> pd.DataFrame:
    converted_df = statement_df.copy()
    converted_df["debit"] = (
        converted_df["amount"].where(converted_df["amount"] < 0).abs()
    )
    converted_df["credit"] = converted_df["amount"].where(converted_df["amount"] > 0)
    return converted_df


raw_df = load_all_statements()
filtered_df = remove_non_transactions(raw_df)
trade_parsed_df = parse_trade_descriptions(filtered_df)
div_parsed_df = parse_div_description(trade_parsed_df)
nrt_parsed_df = parse_nrt_description(div_parsed_df)
cont_parsed_df = parse_cont_description(nrt_parsed_df)
fplint_parsed_df = parse_fplint_description(cont_parsed_df)
stkdis_parsed_df = parse_stkdis_description(fplint_parsed_df)
trfin_parsed_df = parse_trfin_description(stkdis_parsed_df)
fully_parsed_df = parse_wd_description(trfin_parsed_df)
df = add_debit_credit_columns(fully_parsed_df)


if __name__ == "__main__":
    print(f"\nStatement files: {raw_df['source_file'].nunique()}")
    print(f"Rows: {len(df)}")
    print(f"Columns: {list(df.columns)}")
