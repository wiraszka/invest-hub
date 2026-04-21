from fastapi import APIRouter, File, Header, HTTPException, UploadFile

from services.db import get_transactions, replace_transactions
from services.investments import build_positions, parse_csv

router = APIRouter()


def _require_user(x_user_id: str | None) -> str:
    if not x_user_id:
        raise HTTPException(status_code=401, detail="Missing X-User-Id header")
    return x_user_id


@router.post("/api/investments/upload")
async def upload_transactions(
    file: UploadFile = File(...),
    x_user_id: str | None = Header(default=None),
) -> dict:
    user_id = _require_user(x_user_id)
    content = (await file.read()).decode("utf-8")
    transactions = parse_csv(content)
    replace_transactions(user_id, transactions)
    return {"count": len(transactions)}


@router.get("/api/investments/positions")
def get_positions(
    x_user_id: str | None = Header(default=None),
) -> list[dict]:
    user_id = _require_user(x_user_id)
    transactions = get_transactions(user_id)
    return build_positions(transactions)


@router.get("/api/investments/transactions")
def get_all_transactions(
    x_user_id: str | None = Header(default=None),
) -> list[dict]:
    user_id = _require_user(x_user_id)
    return get_transactions(user_id)
