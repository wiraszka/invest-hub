from __future__ import annotations

import importlib.util
import tempfile
import unittest
from pathlib import Path

import pandas as pd


MODULE_PATH = Path(__file__).with_name("ws-statement-parser.py")
SPEC = importlib.util.spec_from_file_location("ws_statement_parser", MODULE_PATH)
ws_statement_parser = importlib.util.module_from_spec(SPEC)
assert SPEC.loader is not None
SPEC.loader.exec_module(ws_statement_parser)


BASE_COLUMNS = ["date", "transaction", "description", "amount", "balance", "currency"]


class StatementParserTests(unittest.TestCase):
    def make_df(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows, columns=BASE_COLUMNS)

    def test_load_statement_preserves_columns_and_converts_types(self) -> None:
        csv_content = """date,transaction,description,amount,balance,currency
2025-12-16,DIV,Dividend received,24.54,1000.00,CAD
2025-12-16,NRT,Non-resident tax (executed at 2025-12-16),-3.69,996.31,CAD
"""
        with tempfile.TemporaryDirectory() as tmp_dir:
            csv_path = Path(tmp_dir) / "statement.csv"
            csv_path.write_text(csv_content)
            df = ws_statement_parser.load_statement(csv_path)

        self.assertEqual(list(df.columns), BASE_COLUMNS + ["source_file"])
        self.assertTrue(pd.api.types.is_datetime64_any_dtype(df["date"]))
        self.assertTrue(pd.api.types.is_numeric_dtype(df["amount"]))
        self.assertTrue(pd.api.types.is_numeric_dtype(df["balance"]))
        self.assertEqual(df.loc[0, "source_file"], "statement.csv")

    def test_remove_non_transactions_filters_only_target_rows(self) -> None:
        df = self.make_df(
            [
                {"date": "2025-12-01", "transaction": "BUY", "description": "a", "amount": -10, "balance": 90, "currency": "CAD"},
                {"date": "2025-12-01", "transaction": "LOAN", "description": "b", "amount": 0, "balance": 90, "currency": "CAD"},
                {"date": "2025-12-01", "transaction": "RECALL", "description": "c", "amount": 0, "balance": 90, "currency": "CAD"},
                {"date": "2025-12-01", "transaction": "STKREORG", "description": "d", "amount": 0, "balance": 90, "currency": "CAD"},
                {"date": "2025-12-01", "transaction": "DIV", "description": "e", "amount": 1, "balance": 91, "currency": "CAD"},
            ]
        )

        filtered_df = ws_statement_parser.remove_non_transactions(df)

        self.assertEqual(filtered_df["transaction"].tolist(), ["BUY", "DIV"])
        self.assertEqual(filtered_df.index.tolist(), [0, 1])

    def test_parse_trade_descriptions_parses_unpriced_buy_and_priced_sell(self) -> None:
        df = self.make_df(
            [
                {
                    "date": "2025-12-16",
                    "transaction": "BUY",
                    "description": "EFR - Energy Fuels Inc.: Bought 3.0000 shares (executed at 2025-12-16)",
                    "amount": -103.53,
                    "balance": 1000,
                    "currency": "CAD",
                },
                {
                    "date": "2025-12-17",
                    "transaction": "SELL",
                    "description": "SBT - Purpose Silver Bullion Fund - ETF Currency Hedged Units: Sold 5.0000 shares at $54.44 per share (executed at 2025-12-17)",
                    "amount": 272.20,
                    "balance": 1272.20,
                    "currency": "CAD",
                },
            ]
        )

        parsed_df = ws_statement_parser.parse_trade_descriptions(df)

        self.assertEqual(parsed_df.loc[0, "ticker"], "EFR")
        self.assertEqual(parsed_df.loc[0, "company_name"], "Energy Fuels Inc.")
        self.assertEqual(parsed_df.loc[0, "type"], "Bought")
        self.assertAlmostEqual(parsed_df.loc[0, "share_count"], 3.0)
        self.assertTrue(pd.isna(parsed_df.loc[0, "price"]))
        self.assertEqual(str(parsed_df.loc[0, "execution_date"].date()), "2025-12-16")
        self.assertEqual(parsed_df.loc[1, "type"], "Sold")
        self.assertAlmostEqual(parsed_df.loc[1, "price"], 54.44)

    def test_parse_trade_descriptions_captures_optional_fx_rate(self) -> None:
        df = self.make_df(
            [
                {
                    "date": "2025-12-17",
                    "transaction": "BUY",
                    "description": "UNH - Unitedhealth Group Inc: Bought 0.0448 shares (executed at 2025-12-16), FX Rate: 1.4011",
                    "amount": -10.0,
                    "balance": 990.0,
                    "currency": "CAD",
                }
            ]
        )

        parsed_df = ws_statement_parser.parse_trade_descriptions(df)

        self.assertAlmostEqual(parsed_df.loc[0, "fx_rate"], 1.4011)

    def test_parse_trade_descriptions_leaves_non_trade_rows_unparsed(self) -> None:
        df = self.make_df(
            [
                {
                    "date": "2025-12-16",
                    "transaction": "FPLINT",
                    "description": "Stock lending monthly interest payment, FX Rate: 1.3854",
                    "amount": 0.01,
                    "balance": 1000,
                    "currency": "CAD",
                }
            ]
        )

        parsed_df = ws_statement_parser.parse_trade_descriptions(df)

        self.assertTrue(pd.isna(parsed_df.loc[0, "ticker"]))
        self.assertTrue(pd.isna(parsed_df.loc[0, "execution_date"]))

    def test_parse_div_description_parses_dividend_with_fx_rate(self) -> None:
        df = self.make_df(
            [
                {
                    "date": "2025-12-16",
                    "transaction": "DIV",
                    "description": "UNH - Unitedhealth Group Inc: Cash dividend distribution, received on 2025-12-16, record date of 2025-12-08, FX Rate: 1.3807",
                    "amount": 24.54,
                    "balance": 1000,
                    "currency": "CAD",
                }
            ]
        )

        parsed_df = ws_statement_parser.parse_div_description(
            ws_statement_parser.parse_trade_descriptions(df)
        )

        self.assertEqual(parsed_df.loc[0, "ticker"], "UNH")
        self.assertEqual(parsed_df.loc[0, "company_name"], "Unitedhealth Group Inc")
        self.assertEqual(parsed_df.loc[0, "type"], "Cash dividend distribution")
        self.assertEqual(str(parsed_df.loc[0, "execution_date"].date()), "2025-12-16")
        self.assertAlmostEqual(parsed_df.loc[0, "fx_rate"], 1.3807)

    def test_parse_div_description_handles_missing_fx_rate(self) -> None:
        df = self.make_df(
            [
                {
                    "date": "2025-12-16",
                    "transaction": "DIV",
                    "description": "ABC - Example Corp: Cash dividend distribution, received on 2025-12-16, record date of 2025-12-08",
                    "amount": 10.0,
                    "balance": 1000,
                    "currency": "CAD",
                }
            ]
        )

        parsed_df = ws_statement_parser.parse_div_description(
            ws_statement_parser.parse_trade_descriptions(df)
        )

        self.assertEqual(parsed_df.loc[0, "ticker"], "ABC")
        self.assertTrue(pd.isna(parsed_df.loc[0, "fx_rate"]))

    def test_parse_nrt_description_parses_tax_row(self) -> None:
        df = self.make_df(
            [
                {
                    "date": "2025-12-16",
                    "transaction": "NRT",
                    "description": "Non-resident tax (executed at 2025-12-16)",
                    "amount": -3.69,
                    "balance": 996.31,
                    "currency": "CAD",
                }
            ]
        )

        parsed_df = ws_statement_parser.parse_nrt_description(df)

        self.assertEqual(parsed_df.loc[0, "type"], "Non-resident tax")
        self.assertEqual(str(parsed_df.loc[0, "execution_date"].date()), "2025-12-16")

    def test_parse_cont_description_parses_contribution(self) -> None:
        df = self.make_df(
            [
                {
                    "date": "2025-07-25",
                    "transaction": "CONT",
                    "description": "Contribution (executed at 2025-07-25)",
                    "amount": 1000.0,
                    "balance": 1000.0,
                    "currency": "CAD",
                }
            ]
        )

        parsed_df = ws_statement_parser.parse_cont_description(df)

        self.assertEqual(parsed_df.loc[0, "type"], "Contribution")
        self.assertEqual(str(parsed_df.loc[0, "execution_date"].date()), "2025-07-25")

    def test_parse_fplint_description_parses_interest_and_optional_fx(self) -> None:
        df = self.make_df(
            [
                {
                    "date": "2025-12-15",
                    "transaction": "FPLINT",
                    "description": "Stock lending monthly interest payment, FX Rate: 1.3854",
                    "amount": 0.01,
                    "balance": 1000.0,
                    "currency": "CAD",
                },
                {
                    "date": "2025-11-15",
                    "transaction": "FPLINT",
                    "description": "Stock lending monthly interest payment",
                    "amount": 0.02,
                    "balance": 1000.0,
                    "currency": "CAD",
                },
            ]
        )

        parsed_df = ws_statement_parser.parse_fplint_description(df)

        self.assertEqual(parsed_df.loc[0, "type"], "Stock lending monthly interest payment")
        self.assertAlmostEqual(parsed_df.loc[0, "fx_rate"], 1.3854)
        self.assertTrue(pd.isna(parsed_df.loc[1, "fx_rate"]))

    def test_parse_stkdis_description_parses_distribution_into_share_count(self) -> None:
        df = self.make_df(
            [
                {
                    "date": "2025-11-14",
                    "transaction": "STKDIS",
                    "description": "ELE - Elemental Altus Royalties Corp: Distribution of -30.0000 shares (executed at 2025-11-14)",
                    "amount": 0.0,
                    "balance": 1000.0,
                    "currency": "CAD",
                }
            ]
        )

        parsed_df = ws_statement_parser.parse_stkdis_description(df)

        self.assertEqual(parsed_df.loc[0, "ticker"], "ELE")
        self.assertEqual(parsed_df.loc[0, "company_name"], "Elemental Altus Royalties Corp")
        self.assertEqual(parsed_df.loc[0, "type"], "Distribution of")
        self.assertAlmostEqual(parsed_df.loc[0, "share_count"], -30.0)
        self.assertEqual(str(parsed_df.loc[0, "execution_date"].date()), "2025-11-14")

    def test_parse_trfin_description_parses_transfer(self) -> None:
        df = self.make_df(
            [
                {
                    "date": "2025-07-14",
                    "transaction": "TRFIN",
                    "description": "Money transfer into the account (executed at 2025-07-14)",
                    "amount": 100.0,
                    "balance": 100.0,
                    "currency": "CAD",
                }
            ]
        )

        parsed_df = ws_statement_parser.parse_trfin_description(df)

        self.assertEqual(parsed_df.loc[0, "type"], "Money transfer into the account")
        self.assertEqual(str(parsed_df.loc[0, "execution_date"].date()), "2025-07-14")

    def test_parse_wd_description_parses_withdrawal(self) -> None:
        df = self.make_df(
            [
                {
                    "date": "2025-08-16",
                    "transaction": "WD",
                    "description": "Non-contribution withdrawal (executed at 2025-08-16)",
                    "amount": -50.0,
                    "balance": 50.0,
                    "currency": "CAD",
                }
            ]
        )

        parsed_df = ws_statement_parser.parse_wd_description(df)

        self.assertEqual(parsed_df.loc[0, "type"], "Non-contribution withdrawal")
        self.assertEqual(str(parsed_df.loc[0, "execution_date"].date()), "2025-08-16")

    def test_add_debit_credit_columns_splits_signed_amounts(self) -> None:
        df = self.make_df(
            [
                {"date": "2025-12-16", "transaction": "BUY", "description": "a", "amount": -103.53, "balance": 1000, "currency": "CAD"},
                {"date": "2025-12-16", "transaction": "DIV", "description": "b", "amount": 24.54, "balance": 1024.54, "currency": "CAD"},
                {"date": "2025-12-16", "transaction": "ZERO", "description": "c", "amount": 0.0, "balance": 1024.54, "currency": "CAD"},
            ]
        )

        converted_df = ws_statement_parser.add_debit_credit_columns(df)

        self.assertAlmostEqual(converted_df.loc[0, "debit"], 103.53)
        self.assertTrue(pd.isna(converted_df.loc[0, "credit"]))
        self.assertAlmostEqual(converted_df.loc[1, "credit"], 24.54)
        self.assertTrue(pd.isna(converted_df.loc[1, "debit"]))
        self.assertTrue(pd.isna(converted_df.loc[2, "debit"]))
        self.assertTrue(pd.isna(converted_df.loc[2, "credit"]))

    def test_full_pipeline_over_all_14_statements_populates_expected_fields(self) -> None:
        files = sorted(Path(__file__).with_name("ws-statements").glob("*.csv"))
        raw_df = pd.concat([ws_statement_parser.load_statement(path) for path in files], ignore_index=True)

        filtered_df = ws_statement_parser.remove_non_transactions(raw_df)
        trade_df = ws_statement_parser.parse_trade_descriptions(filtered_df)
        div_df = ws_statement_parser.parse_div_description(trade_df)
        nrt_df = ws_statement_parser.parse_nrt_description(div_df)
        cont_df = ws_statement_parser.parse_cont_description(nrt_df)
        fplint_df = ws_statement_parser.parse_fplint_description(cont_df)
        stkdis_df = ws_statement_parser.parse_stkdis_description(fplint_df)
        trfin_df = ws_statement_parser.parse_trfin_description(stkdis_df)
        final_df = ws_statement_parser.parse_wd_description(trfin_df)
        final_df = ws_statement_parser.add_debit_credit_columns(final_df)

        self.assertEqual(len(files), 14)
        self.assertEqual(sorted(final_df["transaction"].unique().tolist()), [
            "BUY", "CONT", "DIV", "FPLINT", "NRT", "SELL", "STKDIS", "TRFIN", "WD"
        ])

        checks = [
            ("BUY", "ticker"),
            ("BUY", "execution_date"),
            ("SELL", "ticker"),
            ("SELL", "execution_date"),
            ("DIV", "ticker"),
            ("NRT", "type"),
            ("CONT", "type"),
            ("FPLINT", "type"),
            ("STKDIS", "share_count"),
            ("TRFIN", "type"),
            ("WD", "type"),
        ]
        for transaction, field in checks:
            subset = final_df[final_df["transaction"].eq(transaction)]
            self.assertFalse(subset.empty)
            self.assertFalse(subset[field].isna().any(), msg=f"{transaction} missing {field}")


if __name__ == "__main__":
    unittest.main()
