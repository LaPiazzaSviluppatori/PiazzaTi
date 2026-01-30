from fastapi import APIRouter, Request, Depends, HTTPException
from sqlalchemy.orm import Session
from ..database import get_db
from ..models.document import Document
import datetime
from fastapi.responses import JSONResponse
import os
import uuid
import json



INPUT_FOLDER = "/opt/piazzati/backend/NLP/data/jds"

router = APIRouter()

@router.post("/jd/upload")
async def upload_jd(request: Request):
    @router.post("/jd/create")
    async def create_jd(request: Request, db: Session = Depends(get_db)):
        """
        Crea una nuova Job Description (JD) nel database come Document.
        """
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
                status="draft"
            )
            db.add(doc)
            db.commit()
            db.refresh(doc)
            return {"status": "ok", "id": str(doc.id)}
        except Exception as e:
            raise HTTPException(status_code=500, detail=str(e))
    import sys
    try:
        jd_data = await request.json()
        print("[JD UPLOAD] Ricevuta richiesta:", jd_data, file=sys.stderr)
        filename = f"jd_{uuid.uuid4().hex}.json"
        filepath = os.path.join(INPUT_FOLDER, filename)
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(jd_data, f, ensure_ascii=False, indent=2)
        print(f"[JD UPLOAD] File salvato: {filepath}", file=sys.stderr)
        # Ora la generazione embedding JD e il matching sono gestiti solo dal batch processor.
        return JSONResponse({"status": "ok", "filename": filename})
    except PermissionError as e:
        print(f"[JD UPLOAD] PermissionError: {e}", file=sys.stderr)
        return JSONResponse({"status": "error", "detail": "Permission denied", "message": str(e)}, status_code=500)
    except Exception as e:
        print(f"[JD UPLOAD] Unexpected error: {e}", file=sys.stderr)
        return JSONResponse({"status": "error", "detail": "Unexpected error", "message": str(e)}, status_code=500)
