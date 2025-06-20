# @role: API endpoint to fetch paper/live P&L summaries
# @used_by: project_map.py
# @filter_type: system
# @tags: router, pnl, api
from fastapi import APIRouter, HTTPException
from db.tinydb.client import get_table
import logging

router = APIRouter()
logger = logging.getLogger("pnl_router")

@router.get("/pnl")
def get_pnl_data():
    try:
        db = get_table("pnl")
        data = db.all()
        logger.info("Returned %d P&L records", len(data))
        return data
    except Exception as e:
        logger.exception("Failed to fetch P&L data")
        raise HTTPException(status_code=500, detail="Error reading P&L data")