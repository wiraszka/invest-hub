from unittest.mock import MagicMock, patch

import pytest

from services.llm import classify_company, run_analysis

MOCK_FILING = "This is a 10-K filing for a revenue-generating company."
MOCK_PROMPT = "You are an expert analyst. Analyze the following filing."
MOCK_ANALYSIS = "## Company Analysis\n\nSome analysis here."


def _mock_message(text: str) -> MagicMock:
    content_block = MagicMock()
    content_block.text = text
    msg = MagicMock()
    msg.content = [content_block]
    return msg


def test_classify_company_returns_valid_type():
    with (
        patch("services.llm._client") as mock_client,
        patch("services.llm.get_prompt", return_value=MOCK_PROMPT),
    ):
        mock_client.return_value.messages.create.return_value = _mock_message("mining-company")

        result = classify_company(MOCK_FILING)

    assert result == "mining-company"


def test_classify_company_falls_back_on_unknown_type():
    with patch("services.llm._client") as mock_client:
        mock_client.return_value.messages.create.return_value = _mock_message("something-unknown")

        result = classify_company(MOCK_FILING)

    assert result == "revenue-generating"


def test_run_analysis_returns_markdown():
    with (
        patch("services.llm.get_prompt", return_value=MOCK_PROMPT),
        patch("services.llm._client") as mock_client,
    ):
        mock_client.return_value.messages.create.return_value = _mock_message(MOCK_ANALYSIS)

        result = run_analysis("AAPL", "revenue-generating", MOCK_FILING)

    assert result == MOCK_ANALYSIS


def test_run_analysis_raises_when_prompt_missing():
    with patch("services.llm.get_prompt", return_value=None):
        with pytest.raises(ValueError, match="No prompt found"):
            run_analysis("AAPL", "revenue-generating", MOCK_FILING)
