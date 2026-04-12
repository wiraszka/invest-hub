from fastapi import FastAPI

from routers import analysis, price, search

app = FastAPI()

app.include_router(search.router)
app.include_router(price.router)
app.include_router(analysis.router)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok"}
