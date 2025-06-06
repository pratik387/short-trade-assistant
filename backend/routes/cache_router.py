from fastapi import APIRouter
from backend.jobs.refresh_instrument_cache import refresh_index_cache

router = APIRouter()

@router.post("/api/refresh-index-cache")
def refresh_index_cache_route():
    return refresh_index_cache()
