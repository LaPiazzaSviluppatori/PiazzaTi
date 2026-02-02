import os
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

# Servizio esterno di matching basato su NLP/single_match.py
# Di default si aspetta un container raggiungibile come "matcher" sulla rete Docker,
# con endpoint GET /api/match_cv_jd?user_id=...&jd_id=...
MATCHER_URL = os.getenv("MATCHER_URL", "http://matcher:8000/api/match_cv_jd")


class MatchRequest(BaseModel):
    cv_path: str  # in pratica user_id del candidato
    jd_path: str  # jd_id della job description


@router.post("/match_cv_jd")
async def proxy_match_cv_jd(request: MatchRequest):
    """Proxy verso il servizio di matching (single_match.py).

    Riceve cv_path/jd_path dal frontend e li inoltra come
    user_id/jd_id al servizio esterno esposto da single_match.py.
    """
    try:
        params = {"user_id": request.cv_path, "jd_id": request.jd_path}
        response = requests.get(MATCHER_URL, params=params, timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Matcher service error: {str(e)}")
