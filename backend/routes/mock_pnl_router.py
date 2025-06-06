from fastapi import APIRouter
from tinydb import TinyDB

router = APIRouter()

MOCK_PNL_PATH = "backend/db/tables/mock_pnl.json"

@router.get("/api/mock-pnl")
def get_mock_pnl():
    db = TinyDB(MOCK_PNL_PATH)
    return db.all()
