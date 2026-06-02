from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from core.exceptions import ProviderUnavailableError
from db.pg import get_db_session
from models.market_data import AnalysisData, AnalysisReport, AnalysisResult
from routers.analysis import router

app = FastAPI()
app.include_router(router)


async def _mock_session():
    session = MagicMock()
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=None)
    yield session


app.dependency_overrides[get_db_session] = _mock_session


def _make_data() -> AnalysisData:
    return AnalysisData(
        ticker="AAPL",
        company_name="Apple Inc.",
        exchange="NASDAQ",
        currency="USD",
        sector="Technology",
        industry="Software",
        template_key="general",
        generated_at=datetime.now(timezone.utc),
    )


def _make_analyze_result() -> AnalysisResult:
    return AnalysisResult(
        ticker="AAPL",
        independence="independent",
        chart_data={"revenue_by_segment": None},
        analyzed_at=datetime.now(timezone.utc),
    )


def _make_report() -> AnalysisReport:
    return AnalysisReport(
        ticker="AAPL",
        report_template="general",
        independence="independent",
        report_markdown="### Company Snapshot\n- Apple makes iPhones.",
        generated_at=datetime.now(timezone.utc),
    )


@pytest.fixture
def client():
    return AsyncClient(transport=ASGITransport(app=app), base_url="http://test")


class TestGetAnalysisData:
    async def test_returns_cached_data(self, client: AsyncClient) -> None:
        with patch(
            "routers.analysis.analysis.get_cached_data",
            new=AsyncMock(return_value=_make_data()),
        ):
            async with client as c:
                response = await c.get("/api/v1/analysis/AAPL/data")

        assert response.status_code == 200
        body = response.json()
        assert body["ticker"] == "AAPL"
        assert body["company_name"] == "Apple Inc."
        assert body["template_key"] == "general"

    async def test_returns_404_when_no_data(self, client: AsyncClient) -> None:
        with patch(
            "routers.analysis.analysis.get_cached_data",
            new=AsyncMock(return_value=None),
        ):
            async with client as c:
                response = await c.get("/api/v1/analysis/AAPL/data")

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "DATA_NOT_FOUND"

    async def test_lowercase_ticker_rejected_by_path_validation(
        self, client: AsyncClient
    ) -> None:
        async with client as c:
            response = await c.get("/api/v1/analysis/aapl/data")

        assert response.status_code == 422


class TestPostAnalysisData:
    async def test_returns_generated_data(self, client: AsyncClient) -> None:
        with patch(
            "routers.analysis.analysis.run_providers",
            new=AsyncMock(return_value=_make_data()),
        ):
            async with client as c:
                response = await c.post("/api/v1/analysis/AAPL/data")

        assert response.status_code == 200
        assert response.json()["ticker"] == "AAPL"

    async def test_returns_503_on_provider_unavailable(
        self, client: AsyncClient
    ) -> None:
        with patch(
            "routers.analysis.analysis.run_providers",
            new=AsyncMock(side_effect=ProviderUnavailableError("AAPL", [])),
        ):
            async with client as c:
                response = await c.post("/api/v1/analysis/AAPL/data")

        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "PROVIDER_UNAVAILABLE"

    async def test_returns_502_on_unexpected_error(self, client: AsyncClient) -> None:
        with patch(
            "routers.analysis.analysis.run_providers",
            new=AsyncMock(side_effect=RuntimeError("something exploded")),
        ):
            async with client as c:
                response = await c.post("/api/v1/analysis/AAPL/data")

        assert response.status_code == 502
        assert response.json()["detail"]["code"] == "PIPELINE_ERROR"

    async def test_invalid_ticker_returns_422(self, client: AsyncClient) -> None:
        async with client as c:
            response = await c.post("/api/v1/analysis/invalid ticker!/data")

        assert response.status_code == 422


class TestGetAnalysisReport:
    async def test_returns_cached_report(self, client: AsyncClient) -> None:
        with patch(
            "routers.analysis.analysis.get_cached_report",
            new=AsyncMock(return_value=_make_report()),
        ):
            async with client as c:
                response = await c.get("/api/v1/analysis/AAPL/report")

        assert response.status_code == 200
        body = response.json()
        assert body["ticker"] == "AAPL"
        assert "report_markdown" in body

    async def test_returns_404_when_no_report(self, client: AsyncClient) -> None:
        with patch(
            "routers.analysis.analysis.get_cached_report",
            new=AsyncMock(return_value=None),
        ):
            async with client as c:
                response = await c.get("/api/v1/analysis/AAPL/report")

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "REPORT_NOT_FOUND"


class TestPostAnalysisReport:
    async def test_returns_generated_report(self, client: AsyncClient) -> None:
        with patch(
            "routers.analysis.analysis.run_report",
            new=AsyncMock(return_value=_make_report()),
        ):
            async with client as c:
                response = await c.post("/api/v1/analysis/AAPL/report")

        assert response.status_code == 200
        assert (
            response.json()["report_markdown"]
            == "### Company Snapshot\n- Apple makes iPhones."
        )

    async def test_returns_503_on_provider_unavailable(
        self, client: AsyncClient
    ) -> None:
        with patch(
            "routers.analysis.analysis.run_report",
            new=AsyncMock(side_effect=ProviderUnavailableError("AAPL", [])),
        ):
            async with client as c:
                response = await c.post("/api/v1/analysis/AAPL/report")

        assert response.status_code == 503

    async def test_returns_422_on_classification_error(
        self, client: AsyncClient
    ) -> None:
        with patch(
            "routers.analysis.analysis.run_report",
            new=AsyncMock(
                side_effect=ValueError("analyzer failed to classify company")
            ),
        ):
            async with client as c:
                response = await c.post("/api/v1/analysis/AAPL/report")

        assert response.status_code == 422
        assert response.json()["detail"]["code"] == "CLASSIFICATION_ERROR"

    async def test_force_param_is_passed_through(self, client: AsyncClient) -> None:
        with patch(
            "routers.analysis.analysis.run_report",
            new=AsyncMock(return_value=_make_report()),
        ) as mock:
            async with client as c:
                await c.post("/api/v1/analysis/AAPL/report?force=true")

        _, kwargs = mock.call_args
        assert kwargs.get("force") is True


class TestGetAnalysisResult:
    async def test_returns_cached_result(self, client: AsyncClient) -> None:
        with patch(
            "routers.analysis.analysis.get_cached_analyze",
            new=AsyncMock(return_value=_make_analyze_result()),
        ):
            async with client as c:
                response = await c.get("/api/v1/analysis/AAPL/analyze")

        assert response.status_code == 200
        body = response.json()
        assert body["ticker"] == "AAPL"
        assert body["independence"] == "independent"
        assert "chart_data" in body

    async def test_returns_404_when_no_result(self, client: AsyncClient) -> None:
        with patch(
            "routers.analysis.analysis.get_cached_analyze",
            new=AsyncMock(return_value=None),
        ):
            async with client as c:
                response = await c.get("/api/v1/analysis/AAPL/analyze")

        assert response.status_code == 404
        assert response.json()["detail"]["code"] == "ANALYZE_NOT_FOUND"


class TestPostAnalysisResult:
    async def test_returns_generated_result(self, client: AsyncClient) -> None:
        with patch(
            "routers.analysis.analysis.run_analyze",
            new=AsyncMock(return_value=_make_analyze_result()),
        ):
            async with client as c:
                response = await c.post("/api/v1/analysis/AAPL/analyze")

        assert response.status_code == 200
        body = response.json()
        assert body["ticker"] == "AAPL"
        assert body["independence"] == "independent"

    async def test_returns_503_on_provider_unavailable(
        self, client: AsyncClient
    ) -> None:
        with patch(
            "routers.analysis.analysis.run_analyze",
            new=AsyncMock(side_effect=ProviderUnavailableError("AAPL", [])),
        ):
            async with client as c:
                response = await c.post("/api/v1/analysis/AAPL/analyze")

        assert response.status_code == 503
        assert response.json()["detail"]["code"] == "PROVIDER_UNAVAILABLE"

    async def test_returns_502_on_unexpected_error(self, client: AsyncClient) -> None:
        with patch(
            "routers.analysis.analysis.run_analyze",
            new=AsyncMock(side_effect=RuntimeError("something exploded")),
        ):
            async with client as c:
                response = await c.post("/api/v1/analysis/AAPL/analyze")

        assert response.status_code == 502
        assert response.json()["detail"]["code"] == "PIPELINE_ERROR"

    async def test_force_param_is_passed_through(self, client: AsyncClient) -> None:
        with patch(
            "routers.analysis.analysis.run_analyze",
            new=AsyncMock(return_value=_make_analyze_result()),
        ) as mock:
            async with client as c:
                await c.post("/api/v1/analysis/AAPL/analyze?force=true")

        _, kwargs = mock.call_args
        assert kwargs.get("force") is True
