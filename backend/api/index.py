from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from routers import analysis, price, search, trends

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "https://invest-hub-frontend-six.vercel.app",
    ],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(search.router)
app.include_router(price.router)
app.include_router(analysis.router)
app.include_router(trends.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
