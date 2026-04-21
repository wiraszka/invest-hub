from unittest.mock import MagicMock, patch

from services.llm import _MERGER_NOTICE, classify_and_extract, generate_snapshot

MOCK_FILING = "This is a 10-K filing excerpt for a revenue-generating software company."
MOCK_SNAPSHOT = "- A revenue-generating software company.\n- Operates globally."


def _mock_message(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    msg = MagicMock()
    msg.content = [content_block]
    return msg


def test_classify_and_extract_returns_valid_structure():
    json_response = '{"company_type": "revenue-generating", "company_independence": "independent", "charts": {"capital_structure": {"market_cap_usd": 500000000, "net_debt_usd": 50000000}, "revenue_by_segment": null, "cash_burn": null}}'

    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(
            json_response
        )

        result = classify_and_extract(MOCK_FILING)

    assert result["company_type"] == "revenue-generating"
    assert result["company_independence"] == "independent"
    assert result["charts"]["capital_structure"]["market_cap_usd"] == 500_000_000
    assert result["charts"]["revenue_by_segment"] is None


def test_classify_and_extract_falls_back_on_unknown_type():
    json_response = '{"company_type": "something-unknown", "company_independence": "independent", "charts": {"capital_structure": null, "revenue_by_segment": null, "cash_burn": null}}'

    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(
            json_response
        )

        result = classify_and_extract(MOCK_FILING)

    assert result["company_type"] == "revenue-generating"


def test_classify_and_extract_falls_back_on_unknown_independence():
    json_response = '{"company_type": "revenue-generating", "company_independence": "something-unknown", "charts": {"capital_structure": null, "revenue_by_segment": null, "cash_burn": null}}'

    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(
            json_response
        )

        result = classify_and_extract(MOCK_FILING)

    assert result["company_independence"] == "independent"


def test_classify_and_extract_handles_json_in_prose():
    """LLM sometimes wraps JSON in markdown code fences — should still parse."""
    json_response = '```json\n{"company_type": "pre-revenue", "company_independence": "independent", "charts": {"capital_structure": null, "revenue_by_segment": null, "cash_burn": {"annual_burn_usd": 5000000}}}\n```'

    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(
            json_response
        )

        result = classify_and_extract(MOCK_FILING)

    assert result["company_type"] == "pre-revenue"
    assert result["charts"]["cash_burn"]["annual_burn_usd"] == 5_000_000


def test_generate_snapshot_returns_prose():
    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(
            MOCK_SNAPSHOT
        )

        result = generate_snapshot("AAPL", "revenue-generating", MOCK_FILING)

    assert result == MOCK_SNAPSHOT


def test_generate_snapshot_appends_merger_notice_when_not_independent():
    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(
            MOCK_SNAPSHOT
        )

        result = generate_snapshot(
            "AAPL", "revenue-generating", MOCK_FILING, "possibly_acquired"
        )

    assert result.endswith(_MERGER_NOTICE)
    assert result.startswith(MOCK_SNAPSHOT)


def test_generate_snapshot_no_merger_notice_when_independent():
    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message(
            MOCK_SNAPSHOT
        )

        result = generate_snapshot(
            "AAPL", "revenue-generating", MOCK_FILING, "independent"
        )

    assert _MERGER_NOTICE not in result
