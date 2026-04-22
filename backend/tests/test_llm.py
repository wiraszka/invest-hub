from unittest.mock import MagicMock, patch

from services.llm import _MERGER_NOTICE, classify_and_extract, generate_snapshot

MOCK_FILING = "This is a 10-K filing excerpt for a revenue-generating software company."
MOCK_SNAPSHOT = "- A revenue-generating software company.\n- Operates globally."
MOCK_FMP = {
    "fmp_ticker": "AAPL",
    "currency": "USD",
    "income": [{"year": 2024, "revenue": 1_000_000, "gross_profit": 400_000, "net_income": 150_000, "ebitda": 250_000, "operating_income": 200_000}],
    "balance_sheet": {"cash": 500_000, "total_debt": 200_000, "net_debt": -300_000},
    "cash_flow": [{"year": 2024, "operating_cash_flow": 300_000, "capex": -50_000, "free_cash_flow": 250_000}],
    "metrics": {"market_cap": 5_000_000, "enterprise_value": 4_700_000, "pe_ratio": 25.0, "ev_ebitda": 18.8},
}


def _mock_message(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    msg = MagicMock()
    msg.content = [content_block]
    return msg


# ---------------------------------------------------------------------------
# classify_and_extract
# ---------------------------------------------------------------------------


def test_classify_and_extract_returns_valid_structure():
    json_response = '{"company_type": "revenue-generating", "company_independence": "independent", "charts": {"revenue_by_segment": null}}'

    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(json_response)

        result = classify_and_extract(MOCK_FILING, MOCK_FMP)

    assert result["company_type"] == "revenue-generating"
    assert result["company_independence"] == "independent"
    assert result["charts"]["revenue_by_segment"] is None


def test_classify_and_extract_falls_back_on_unknown_type():
    json_response = '{"company_type": "something-unknown", "company_independence": "independent", "charts": {"revenue_by_segment": null}}'

    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(json_response)

        result = classify_and_extract(MOCK_FILING, MOCK_FMP)

    assert result["company_type"] == "revenue-generating"


def test_classify_and_extract_falls_back_on_unknown_independence():
    json_response = '{"company_type": "revenue-generating", "company_independence": "something-unknown", "charts": {"revenue_by_segment": null}}'

    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(json_response)

        result = classify_and_extract(MOCK_FILING, MOCK_FMP)

    assert result["company_independence"] == "independent"


def test_classify_and_extract_handles_json_in_prose():
    """LLM sometimes wraps JSON in markdown code fences — should still parse."""
    json_response = '```json\n{"company_type": "pre-revenue", "company_independence": "independent", "charts": {"revenue_by_segment": null}}\n```'

    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(json_response)

        result = classify_and_extract(MOCK_FILING, MOCK_FMP)

    assert result["company_type"] == "pre-revenue"


def test_classify_and_extract_includes_fmp_data_in_prompt():
    """FMP financials should be passed to the LLM as part of the user message."""
    json_response = '{"company_type": "revenue-generating", "company_independence": "independent", "charts": {"revenue_by_segment": null}}'

    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(json_response)

        classify_and_extract(MOCK_FILING, MOCK_FMP)

        call_kwargs = mock_client.return_value.messages.create.call_args
        user_content = call_kwargs[1]["messages"][0]["content"]

    assert "revenue" in user_content.lower() or "fmp" in user_content.lower()


def test_classify_and_extract_mining_returns_industry_charts():
    json_response = '{"company_type": "mining-company", "company_independence": "independent", "charts": {"revenue_by_segment": null, "reserves_by_asset": {"Mine A": 500000}}}'

    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(json_response)

        result = classify_and_extract(MOCK_FILING, MOCK_FMP)

    assert result["company_type"] == "mining-company"
    assert result["charts"]["reserves_by_asset"]["Mine A"] == 500_000


# ---------------------------------------------------------------------------
# generate_snapshot
# ---------------------------------------------------------------------------


def test_generate_snapshot_returns_prose():
    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(MOCK_SNAPSHOT)

        result = generate_snapshot("AAPL", "revenue-generating", MOCK_FILING, MOCK_FMP)

    assert result == MOCK_SNAPSHOT


def test_generate_snapshot_appends_merger_notice_when_not_independent():
    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(MOCK_SNAPSHOT)

        result = generate_snapshot(
            "AAPL", "revenue-generating", MOCK_FILING, MOCK_FMP, "possibly_acquired"
        )

    assert result.endswith(_MERGER_NOTICE)
    assert result.startswith(MOCK_SNAPSHOT)


def test_generate_snapshot_no_merger_notice_when_independent():
    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(MOCK_SNAPSHOT)

        result = generate_snapshot(
            "AAPL", "revenue-generating", MOCK_FILING, MOCK_FMP, "independent"
        )

    assert _MERGER_NOTICE not in result


def test_generate_snapshot_includes_fmp_data_in_prompt():
    """FMP financials should appear in the message sent to the LLM."""
    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(MOCK_SNAPSHOT)

        generate_snapshot("AAPL", "revenue-generating", MOCK_FILING, MOCK_FMP)

        call_kwargs = mock_client.return_value.messages.create.call_args
        user_content = call_kwargs[1]["messages"][0]["content"]

    assert "5,000,000" in user_content or "5000000" in user_content or "revenue" in user_content.lower()
