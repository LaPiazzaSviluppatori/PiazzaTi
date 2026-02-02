import os
import requests
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

MATCHER_URL = os.getenv("MATCHER_URL", "http://matcher:8000/api/match_cv_jd")

class MatchRequest(BaseModel):
    cv_path: str
    jd_path: str

@router.post("/match_cv_jd")
async def proxy_match_cv_jd(request: MatchRequest):
    try:
        response = requests.post(MATCHER_URL, json=request.dict(), timeout=30)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        raise HTTPException(status_code=502, detail=f"Matcher service error: {str(e)}")
