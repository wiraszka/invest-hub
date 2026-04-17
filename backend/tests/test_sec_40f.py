from unittest.mock import MagicMock, patch

from services.sec_40f import fetch_40f_sections

MOCK_INDEX_HTML = """
<html><body>
<table>
<tr>
  <td>FORM-40-F</td><td>form40f.htm</td><td></td><td>40-F</td>
</tr>
<tr>
  <td>ANNUAL INFO FORM</td>
  <td><a href="/Archives/edgar/data/12345/000123456725000001/aif.htm">aif.htm</a></td>
  <td></td>
  <td>EX-99.1</td>
</tr>
</table>
</body></html>
"""

MOCK_AIF_HTML = """
<html><body>
<p>Description of the Business</p>
<p>We are a gold mining company operating in Canada and Mexico.</p>
<p>Risk Factors</p>
<p>We face commodity price risk and geopolitical risk.</p>
<p>Management's Discussion and Analysis</p>
<p>Revenue increased 12% year-over-year driven by higher gold prices.</p>
<p>Financial Statements</p>
</body></html>
"""


def test_fetch_40f_sections_extracts_from_exhibit():
    index_resp = MagicMock()
    index_resp.raise_for_status = lambda: None
    index_resp.text = MOCK_INDEX_HTML

    exhibit_resp = MagicMock()
    exhibit_resp.raise_for_status = lambda: None
    exhibit_resp.text = MOCK_AIF_HTML

    with patch("services.sec_40f.requests.get", side_effect=[index_resp, exhibit_resp]):
        result = fetch_40f_sections("0000012345", "0001234567-25-000001")

    assert "gold mining" in result
    assert "commodity price" in result
    assert "Revenue increased" in result


def test_fetch_40f_sections_raises_when_no_exhibit():
    index_html_no_exhibit = """
    <html><body>
    <table>
    <tr><td>FORM-40-F</td><td>form40f.htm</td><td></td><td>40-F</td></tr>
    </table>
    </body></html>
    """

    index_resp = MagicMock()
    index_resp.raise_for_status = lambda: None
    index_resp.text = index_html_no_exhibit

    import pytest

    with patch("services.sec_40f.requests.get", return_value=index_resp):
        with pytest.raises(ValueError, match="No EX-99.1"):
            fetch_40f_sections("0000012345", "0001234567-25-000001")
