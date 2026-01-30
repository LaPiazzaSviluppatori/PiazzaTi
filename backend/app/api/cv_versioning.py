from fastapi import APIRouter, Query
from fastapi.responses import JSONResponse
import os
import re
import json

CVS_DIR = "/opt/piazzati/backend/NLP/data/cvs/"

router = APIRouter(prefix="/cv", tags=["cv_versioning"])

@router.get("/previous")
async def get_previous_cv(user_id: str = Query(...), current_filename: str = Query(...)):
    match = re.search(rf"{user_id}_(\d{{8}}_\d{{6}})", current_filename)
    if not match:
        return JSONResponse({"previous_filename": None})
    current_ts = match.group(1)
    files = [f for f in os.listdir(CVS_DIR) if f.startswith(user_id) and f.endswith(".json")]
    previous_files = []
    for f in files:
        m = re.search(rf"{user_id}_(\d{{8}}_\d{{6}})", f)
        if m and m.group(1) < current_ts:
            previous_files.append((m.group(1), f))
    if not previous_files:
        return JSONResponse({"previous_filename": None})
    previous_files.sort(reverse=True)
    return JSONResponse({"previous_filename": previous_files[0][1]})

@router.delete("/delete")
async def delete_cv(filename: str = Query(...)):
    file_path = os.path.join(CVS_DIR, filename)
    if os.path.exists(file_path):
        os.remove(file_path)
        return JSONResponse({"deleted": True})
    return JSONResponse({"deleted": False, "error": "File not found"})

@router.get("/get")
async def get_cv(filename: str = Query(...)):
    file_path = os.path.join(CVS_DIR, filename)
    if os.path.exists(file_path):
        with open(file_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return JSONResponse(data)
    return JSONResponse({"error": "File not found"}, status_code=404)
