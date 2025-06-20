# @role: API route for cache clearing and diagnostics
# @used_by: project_map.py
# @filter_type: system
# @tags: router, api, cache
from fastapi import APIRouter
from jobs.refresh_instrument_cache import refresh_index_cache

router = APIRouter()

@router.post("/refresh-index-cache")
def refresh_index_cache_route():
    return refresh_index_cache()