from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.document import Document
import datetime
from fastapi.responses import JSONResponse
import os
import subprocess
import uuid
import json
import sys

INPUT_FOLDER = "/opt/piazzati/backend/NLP/data/jds"

router = APIRouter()


@router.post("/jd/create")
async def create_jd(request: Request, db: Session = Depends(get_db)):
    """Crea una nuova Job Description (JD) nel database come Document."""
    try:
        jd_data = await request.json()
        # Campi minimi richiesti: title, description, language
        title = jd_data.get("title")
        description = jd_data.get("description")
        language = jd_data.get("language", "it")
        if not title or not description:
            raise HTTPException(status_code=400, detail="title e description sono obbligatori")
        doc = Document(
            id=uuid.uuid4(),
            type="jd",
            title=title,
            description_raw=description,
            language=language,
            parsed_json=jd_data,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow(),
            status="draft",
        )
        db.add(doc)
        db.commit()
        db.refresh(doc)
        return {"status": "ok", "id": str(doc.id)}
    except HTTPException:
        # Rilancia HTTPException così com'è
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/jd/upload")
async def upload_jd(request: Request):
    try:
        jd_data = await request.json()
        print("[JD UPLOAD] Ricevuta richiesta:", jd_data, file=sys.stderr)
        filename = f"jd_{uuid.uuid4().hex}.json"
        filepath = os.path.join(INPUT_FOLDER, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(jd_data, f, ensure_ascii=False, indent=2)
        print(f"[JD UPLOAD] File salvato: {filepath}", file=sys.stderr)
        # Lancia la pipeline di normalizzazione e embedding JD in background
        try:
            subprocess.Popen([
                "python", "NLP/normalizzatore.py"
            ], cwd=os.path.dirname(os.path.dirname(os.path.dirname(__file__))))
            print("[JD UPLOAD] Pipeline normalizzazione JD avviata", file=sys.stderr)
        except Exception as e:
            print(f"[JD UPLOAD] Errore avvio pipeline: {e}", file=sys.stderr)
        return JSONResponse({"status": "ok", "filename": filename})
    except PermissionError as e:
        print(f"[JD UPLOAD] PermissionError: {e}", file=sys.stderr)
        return JSONResponse({"status": "error", "detail": "Permission denied", "message": str(e)}, status_code=500)
    except Exception as e:
        print(f"[JD UPLOAD] Unexpected error: {e}", file=sys.stderr)
        return JSONResponse({"status": "error", "detail": "Unexpected error", "message": str(e)}, status_code=500)

@router.get("/jd/list")
async def list_jd(db: Session = Depends(get_db)):
    """Restituisce le prime 20 JD salvate, ordinate per data di creazione decrescente."""
    jds = db.query(Document).filter(Document.type == "jd").order_by(Document.created_at.desc()).limit(20).all()
    # Serializza solo i campi principali
    return [
        {
            "jd_id": str(jd.id),
            "title": jd.title,
            "description": jd.description_raw,
            "language": jd.language,
            "created_at": jd.created_at.isoformat() if jd.created_at else None,
            "requirements": (jd.parsed_json or {}).get("requirements", []),
            "nice_to_have": (jd.parsed_json or {}).get("nice_to_have", []),
        }
        for jd in jds
    ]
