from __future__ import annotations

import logging
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from core.logging import configure_logging, request_id_var
from routers import analysis, investments, market_data, price, search, trends

configure_logging()
logger = logging.getLogger(__name__)

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "https://invest-hub-frontend-six.vercel.app",
        "https://investhub.tech",
        "https://www.investhub.tech",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def correlation_id_middleware(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    token = request_id_var.set(request_id)
    try:
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response
    except Exception as exc:
        logger.exception("Unhandled error", extra={"path": request.url.path})
        return JSONResponse(
            status_code=500,
            content={"error": {"code": "INTERNAL_ERROR", "message": "An unexpected error occurred"}},
            headers={"X-Request-Id": request_id},
        )
    finally:
        request_id_var.reset(token)


app.include_router(search.router)
app.include_router(price.router)
app.include_router(analysis.router)
app.include_router(trends.router)
app.include_router(investments.router)
app.include_router(market_data.router)


@app.get("/api/v1/health")
def health() -> dict:
    return {"status": "ok"}
