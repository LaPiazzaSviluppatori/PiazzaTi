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
from pathlib import Path
import csv

# Cartella condivisa con la pipeline NLP dentro al container backend
# Montata come volume in docker-compose:
#   /var/lib/docker/piazzati-data:/app/NLP/data
INPUT_FOLDER = "/app/NLP/data/jds"

router = APIRouter()


def _save_jd_json_and_start_pipeline(jd_data: dict) -> str:
    """Salva il JSON JD nella cartella condivisa NLP e avvia la pipeline.

    Usato sia da /jd/create (flusso principale) sia da /jd/upload.
    """

    if not isinstance(jd_data, dict):
        jd_data = dict(jd_data)

    jd_id = jd_data.get("jd_id")
    if not jd_id:
        raise HTTPException(status_code=400, detail="jd_id mancante per salvataggio JD")

    os.makedirs(INPUT_FOLDER, exist_ok=True)
    safe_id = str(jd_id).replace(os.sep, "_")
    filename = f"jd_{safe_id}.json"
    filepath = os.path.join(INPUT_FOLDER, filename)

    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(jd_data, f, ensure_ascii=False, indent=2)

    print(f"[JD PIPELINE] File JD salvato: {filepath}", file=sys.stderr)

    # Lancia la pipeline completa JD (JSON -> dataset -> normalizzazione -> embeddings)
    try:
        # In container: __file__ = /app/app/api/jd.py -> project_root = /app
        from pathlib import Path as _Path
        project_root = _Path(__file__).resolve().parents[2]
        subprocess.Popen(
            ["python", "cron_scripts/batch_processor.py", "--process-jd"],
            cwd=str(project_root)
        )
        print("[JD PIPELINE] Pipeline JD completa avviata", file=sys.stderr)
    except Exception as e:
        print(f"[JD PIPELINE] Errore avvio pipeline: {e}", file=sys.stderr)

    return filepath


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
        # Usa un unico identificatore coerente per DB, JSON e pipeline NLP
        doc_id = uuid.uuid4()
        # Assicura che il JSON contenga jd_id allineato a Document.id
        if not isinstance(jd_data, dict):
            jd_data = dict(jd_data)
        jd_data.setdefault("jd_id", str(doc_id))
        doc = Document(
            id=doc_id,
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

        # Salva subito anche il JSON per la pipeline NLP e avvia il batch JD
        try:
            _save_jd_json_and_start_pipeline(jd_data)
        except Exception as e:
            # Non blocca la creazione JD se la pipeline fallisce all'avvio
            print(f"[JD CREATE] Errore avvio pipeline JD: {e}", file=sys.stderr)

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
        # Allinea jd_id per la pipeline NLP:
        # - se jd_id è già presente, lo riusa
        # - se manca ma c'è un campo id (es. Document.id), lo usa come jd_id
        # Non generiamo un nuovo ID qui per evitare inconsistenze.
        if isinstance(jd_data, dict):
            if "jd_id" not in jd_data:
                if "id" in jd_data:
                    jd_data["jd_id"] = str(jd_data["id"])
                else:
                    raise HTTPException(status_code=400, detail="jd_id o id mancante nel payload JD upload")
        filepath = _save_jd_json_and_start_pipeline(jd_data)
        return JSONResponse({"status": "ok", "filename": os.path.basename(filepath)})
    except PermissionError as e:
        print(f"[JD UPLOAD] PermissionError: {e}", file=sys.stderr)
        return JSONResponse({"status": "error", "detail": "Permission denied", "message": str(e)}, status_code=500)
    except Exception as e:
        print(f"[JD UPLOAD] Unexpected error: {e}", file=sys.stderr)
        return JSONResponse({"status": "error", "detail": "Unexpected error", "message": str(e)}, status_code=500)

@router.get("/jd/list")
async def list_jd(db: Session = Depends(get_db)):
    """Restituisce le prime 20 JD salvate, ordinate per data di creazione decrescente.

    Include anche il campo `company` presente nel parsed_json, così il frontend
    può mostrare/filtrare le JD per azienda.
    """
    jds = (
        db.query(Document)
        .filter(Document.type == "jd")
        .order_by(Document.created_at.desc())
        .limit(20)
        .all()
    )

    return [
        {
            "jd_id": str(jd.id),
            "title": jd.title,
            "description": jd.description_raw,
            "language": jd.language,
            "created_at": jd.created_at.isoformat() if jd.created_at else None,
            "requirements": (jd.parsed_json or {}).get("requirements", []),
            "nice_to_have": (jd.parsed_json or {}).get("nice_to_have", []),
            "company": (jd.parsed_json or {}).get("company"),
        }
        for jd in jds
    ]


@router.get("/jd/status")
async def jd_status(jd_id: str | None = None):
    """Ritorna lo stato della pipeline JD.

    Usabile dal frontend per mostrare avanzamento dopo il submit del form JD.
    Se viene passato jd_id, prova a verificare se è presente nei dataset.
    """

    base_nlp = Path("/app/NLP")
    json_dir = base_nlp / "data" / "jds"
    dataset_csv = base_nlp / "Dataset" / "jd_dataset.csv"
    normalized_csv = base_nlp / "Dataset" / "normalized" / "jd_dataset_normalized.csv"
    embeddings_csv = base_nlp / "embeddings" / "jd_embeddings.csv"

    def count_rows(path: Path) -> int:
        if not path.exists():
            return 0
        try:
            with path.open("r", encoding="utf-8") as f:
                reader = csv.reader(f)
                # salta header
                next(reader, None)
                return sum(1 for _ in reader)
        except Exception:
            return 0

    def jd_in_csv(path: Path, jd_id_value: str) -> bool:
        if not path.exists():
            return False
        try:
            with path.open("r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get("jd_id") == jd_id_value:
                        return True
            return False
        except Exception:
            return False

    # Stato globale pipeline
    json_count = len(list(json_dir.glob("*.json"))) if json_dir.exists() else 0
    dataset_rows = count_rows(dataset_csv)
    normalized_rows = count_rows(normalized_csv)
    embeddings_ready = embeddings_csv.exists()

    status = {
        "json_files": json_count,
        "dataset_rows": dataset_rows,
        "normalized_rows": normalized_rows,
        "embeddings_ready": embeddings_ready,
    }

    # Stato specifico per una JD
    if jd_id:
        status["jd"] = {
            "jd_id": jd_id,
            "in_dataset": jd_in_csv(dataset_csv, jd_id),
            "in_normalized": jd_in_csv(normalized_csv, jd_id),
        }

    return status
