from sqlalchemy.orm import Session
from sqlalchemy import and_
from ..database import get_db, SessionLocal
from ..models import Document
import tempfile
import time
import uuid
from pathlib import Path

from ..parsers.ollama_cv_parser import OllamaCVParser
from ..utils.parsing_display import display_parsing_results
from ..services.cv_batch_storage import get_batch_storage
from ..schemas.parsed_document import ParsedDocument, Skill as ParsedSkill, SkillSource
from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    UploadFile,
)
from fastapi import Depends
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from datetime import datetime
from pydantic import BaseModel
import json
import importlib.util
import subprocess
import sys
import logging
from contextlib import nullcontext

router = APIRouter(prefix="/parse", tags=["parse"])

# Module logger
logger = logging.getLogger(__name__)


class SkillUpdateRequest(BaseModel):
    """Payload per aggiornare/aggiungere skill al CV parsato di uno user."""

    skills: list[str]


def _save_parsed_cv_to_db(db: Session, user_id: str, doc_parsed) -> Document:
    """Salva il CV parsato nel DB come ultimo CV (is_latest) per l'utente."""
    if not user_id:
        return None

    # Converte il ParsedDocument in dict serializzabile
    if hasattr(doc_parsed, "model_dump"):
        parsed_json = doc_parsed.model_dump()
    elif hasattr(doc_parsed, "dict"):
        parsed_json = doc_parsed.dict()
    else:
        parsed_json = getattr(doc_parsed, "__dict__", {}).copy()

    # Assicura che parsed_json contenga solo tipi JSON-serializzabili
    parsed_json = jsonable_encoder(parsed_json)

    # Transazione atomica con lock sulla riga
    from sqlalchemy import select

    # Se la Session ha già una transazione aperta (tipico dopo una query),
    # usiamo una nested transaction per evitare "A transaction is already begun"
    tx_ctx = db.begin_nested() if db.in_transaction() else db.begin()

    with tx_ctx:
        # Lock sulla riga del vecchio CV
        old_cv = (
            db.execute(
                select(Document).with_for_update()
                .where(Document.user_id == user_id, Document.type == "cv", Document.is_latest == True)
            ).scalars().first()
        )
        if old_cv:
            old_cv.is_latest = False
            db.add(old_cv)
        # Crea nuovo documento
        new_doc = Document(
            id=uuid.uuid4(),
            user_id=user_id,
            type="cv",
            is_latest=True,
            parsed_json=parsed_json,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
            status="parsed",
        )
        db.add(new_doc)
        db.flush()
        db.refresh(new_doc)
        return new_doc


def _start_batch_process(process_date: str | None = None) -> None:
    """
    Avvia lo script `cron_scripts/batch_processor.py` per la data specificata.
    Se `process_date` è None, usa la data odierna.
    Funzione pensata per essere eseguita in background (BackgroundTasks).
    """
    try:
        pd = process_date or datetime.now().strftime("%Y-%m-%d")
        script_path = Path(__file__).parent.parent.parent / "cron_scripts" / "batch_processor.py"
        if not script_path.exists():
            logger.error("Batch processor script non trovato: %s", script_path)
            return
        cmd = [sys.executable, str(script_path), "--process-date", pd]
        logger.info("Avviando batch processor: %s", " ".join(cmd))
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600)
        if result.returncode != 0:
            logger.error("Batch processor fallito (code=%d): %s", result.returncode, result.stderr)
        else:
            logger.info("Batch processor completato. stdout len=%d", len(result.stdout))
    except Exception as e:
        logger.exception("Errore avviando batch processor: %s", str(e))


@router.post("/upload_db")
async def upload_and_save_cv(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    background: bool = False,
    db: Session = Depends(get_db),
    background_tasks: BackgroundTasks = None,
):
    """Upload CV, parse, salva su Postgres, sostituisce il vecchio CV (is_latest)."""
    if file.content_type not in ("application/pdf",):
        raise HTTPException(status_code=400, detail="Only PDF uploads are accepted")

    tmp_dir = Path(tempfile.gettempdir()) / "piazzati_parsing"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    dest = tmp_dir / f"upload_{file.filename}_{int(time.time())}.pdf"
    content = await file.read()
    dest.write_bytes(content)

    parser = get_parser()
    doc_parsed = parser.parse(str(dest))
    # Propaga anche l'user_id dentro al ParsedDocument, così parsed_json lo contiene sempre
    try:
        doc_parsed.user_id = user_id
    except Exception:
        pass

    new_doc = _save_parsed_cv_to_db(db, user_id, doc_parsed)

    # Avvia pipeline batch (embeddings) in background per la data odierna
    try:
        if background_tasks is not None:
            process_date = datetime.now().strftime("%Y-%m-%d")
            logger.info("Scheduling batch process for date %s (upload_db)", process_date)
            background_tasks.add_task(_start_batch_process, process_date)
    except Exception as e:
        print("Impossibile schedulare batch automatico:", str(e))

    return {"message": "CV caricato e salvato", "document_id": str(new_doc.id)}


@router.get("/user/{user_id}/cv/latest")
def get_latest_cv(user_id: str, db: Session = Depends(get_db)):
    """Recupera l'ultimo CV (is_latest) per uno user_id."""
    doc = db.query(Document).filter_by(user_id=user_id, type='cv', is_latest=True).first()
    if not doc:
        raise HTTPException(status_code=404, detail="CV not found")
    return {
        "id": str(doc.id),
        "user_id": str(doc.user_id),
        "created_at": doc.created_at,
        "updated_at": doc.updated_at,
        "parsed_json": doc.parsed_json,
        "status": doc.status,
    }


@router.post("/user/{user_id}/skills/append")
def append_user_skills(
    user_id: str,
    payload: SkillUpdateRequest,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Aggiunge nuove skill al CV parsato dell'utente e rilancia la pipeline embeddings.

    - Recupera l'ultimo Document di tipo 'cv' per lo user_id
    - Converte parsed_json in ParsedDocument
    - Aggiunge le skill mancanti (case-insensitive)
    - Salva un nuovo Document is_latest nel DB
    - Salva il JSON aggiornato su filesystem per il batch NLP
    - Avvia il batch processor per rigenerare embeddings
    """

    if not payload.skills:
        raise HTTPException(status_code=400, detail="Nessuna skill fornita")

    logger.info("[append_user_skills] Request to append skills for user_id=%s skills=%s", user_id, payload.skills)

    # NB: Document.user_id è UUID; convertiamo esplicitamente la stringa per evitare mismatch silenziosi
    from uuid import UUID
    try:
        user_uuid = UUID(str(user_id))
    except Exception:
        logger.error("[append_user_skills] user_id non è un UUID valido: %s", user_id)
        raise HTTPException(status_code=400, detail="user_id non valido")

    doc = db.query(Document).filter_by(user_id=user_uuid, type="cv", is_latest=True).first()
    if not doc or not doc.parsed_json:
        logger.warning("[append_user_skills] Nessun CV is_latest trovato per user_id=%s", user_uuid)
        raise HTTPException(status_code=404, detail="Nessun CV caricato per questo utente")
    try:
        parsed_doc = ParsedDocument(**doc.parsed_json)
    except Exception as e:  # pragma: no cover - errore raro di deserializzazione
        logger.exception("[append_user_skills] Errore ricostruendo ParsedDocument per doc_id=%s: %s", doc.id, e)
        raise HTTPException(status_code=500, detail=f"Impossibile ricostruire ParsedDocument: {e}")

    existing_names = {s.name.lower() for s in parsed_doc.skills if s.name}
    added: list[str] = []

    for raw_name in payload.skills:
        name = (raw_name or "").strip()
        if not name:
            continue
        lower = name.lower()
        if lower in existing_names:
            continue
        parsed_doc.skills.append(ParsedSkill(name=name, source=SkillSource.heuristic, confidence=0.9))
        existing_names.add(lower)
        added.append(name)

    if not added:
        logger.info(
            "[append_user_skills] Nessuna nuova skill aggiunta per user_id=%s (tutte già presenti)",
            user_uuid,
        )
        return {"message": "Nessuna nuova skill aggiunta (già presenti)", "document_id": str(doc.id)}

    # Salva un nuovo Document come ultimo CV per l'utente
    new_doc = _save_parsed_cv_to_db(db, str(user_uuid), parsed_doc)

    # Salva anche il JSON aggiornato nella cartella batch NLP
    batch_storage = get_batch_storage()
    json_path = batch_storage.save_parsed_cv(parsed_doc, getattr(parsed_doc, "file_name", None))
    logger.info(
        "[append_user_skills] Salvato JSON batch per user_id=%s doc_id=%s path=%s added_skills=%s",
        user_uuid,
        getattr(parsed_doc, "document_id", None) or str(new_doc.id if new_doc else doc.id),
        json_path,
        added,
    )

    # Avvia pipeline batch (embeddings) per la data odierna
    try:
        if background_tasks is not None:
            process_date = datetime.now().strftime("%Y-%m-%d")
            logger.info("[append_user_skills] Scheduling batch process for date %s (skills append)", process_date)
            background_tasks.add_task(_start_batch_process, process_date)
        else:
            logger.warning("[append_user_skills] background_tasks è None, batch non schedulato")
    except Exception as e:  # pragma: no cover - errore non critico
        logger.exception("[append_user_skills] Impossibile schedulare batch automatico dopo append skill: %s", str(e))

    return {
        "message": "Skill aggiornate e pipeline embeddings avviata",
        "document_id": str(new_doc.id) if new_doc else str(doc.id),
        "added_skills": added,
        "json_path": json_path,
    }


# Lazy singleton parser to avoid re-init per request
_parser: OllamaCVParser = None

# In-memory storage for task results (in production, use Redis/DB)
_task_results = {}


def get_parser() -> OllamaCVParser:
    global _parser
    if _parser is None:
        _parser = OllamaCVParser(model="llama3.2:3b")
    return _parser


@router.get("/status")
async def get_parser_status():
    """Check parser and LLM status."""
    parser = get_parser()
    
    llm_status = {
        "llm_available": hasattr(parser, 'llm') and parser.llm is not None,
        "base_url": getattr(parser, 'base_url', 'unknown'),
        "model": getattr(parser, 'model', 'unknown')
    }
    
    # Test Ollama connectivity
    try:
        from ..ollama_integration import check_ollama_api
        ollama_reachable = check_ollama_api(timeout=3)
        llm_status["ollama_reachable"] = ollama_reachable
    except Exception as e:
        llm_status["ollama_reachable"] = False
        llm_status["ollama_error"] = str(e)
    
    return {
        "parser_initialized": parser is not None,
        "parser_version": "v2.1.1-ULTIMATE",
        "llm_status": llm_status
    }


@router.post("/reinitialize-llm")
async def reinitialize_llm(base_url: str = "http://host.docker.internal:11434"):
    """Reinitialize LLM with new base_url."""
    global _parser
    
    try:
        # Create new parser instance with updated base_url
        _parser = OllamaCVParser(model="llama3.2:3b", base_url=base_url)
        
        status = {
            "success": True,
            "llm_available": hasattr(_parser, 'llm') and _parser.llm is not None,
            "base_url": _parser.base_url,
            "model": _parser.model
        }
        
        if status["llm_available"]:
            status["message"] = "LLM successfully reinitialized and connected!"
        else:
            status["message"] = "Parser reinitialized but LLM connection failed"
            
        return status
        
    except Exception as e:
        return {
            "success": False,
            "error": str(e),
            "message": "Failed to reinitialize LLM"
        }


@router.get("/task/{task_id}")
async def get_task_status(task_id: str):
    """Get the status of a background parsing task."""
    if task_id not in _task_results:
        raise HTTPException(status_code=404, detail="Task not found")
    
    result = _task_results[task_id].copy()
    # Assicura che l'id sia sempre presente nella risposta del polling
    if "result" in result and isinstance(result["result"], dict):
        if "id" not in result["result"]:
            # Prova a recuperare user_id da doc o da altri campi
            user_id = result.get("result", {}).get("user_id") or result.get("user_id")
            if user_id:
                result["result"]["id"] = user_id
    
    # Add elapsed time info
    if "started_at" in result:
        elapsed = time.time() - result["started_at"]
        result["elapsed_seconds"] = round(elapsed, 1)
        
        if result["status"] == "processing":
            result["estimated_remaining"] = max(0, 180 - elapsed)  # Estimate 3 minutes total
    
    return result


@router.get("/batch/stats")
async def get_batch_stats():
    """Get statistics about CV files saved for batch processing."""
    batch_storage = get_batch_storage()
    stats = batch_storage.get_batch_stats()
    
    return {
        "batch_processing": {
            "enabled": True,
            "storage_path": str(batch_storage.base_path),
            **stats
        }
    }


@router.post("/batch/process")
async def trigger_batch_processing(
    date: str = None,
    background_tasks: BackgroundTasks = None
):
    """
    Trigger batch processing della pipeline NLP per una data specifica.
    Se date non specificata, processa i CV di oggi.
    """
    if background_tasks is None:
        raise HTTPException(status_code=500, detail="Background tasks unavailable")
    
    process_date = date or datetime.now().strftime("%Y-%m-%d")
    task_id = f"batch_{process_date}_{int(time.time())}"
    
    # Schedule standardized batch starter (uses `cron_scripts/batch_processor.py`)
    background_tasks.add_task(_start_batch_process, process_date)
    
    return JSONResponse(
        status_code=202,
        content={
            "message": f"Batch processing avviato per {process_date}",
            "task_id": task_id,
            "date": process_date,
            "status": "processing"
        }
    )


MULTIPART_AVAILABLE = importlib.util.find_spec("multipart") is not None


if MULTIPART_AVAILABLE:
    @router.post("/upload")
    async def upload_and_parse(
        file: UploadFile = File(...),
        background: bool = True,
        background_tasks: BackgroundTasks = None,
        user_id: str | None = Form(None),
        Tags: str | None = Form(None),
        db: Session = Depends(get_db),
    ):
        """Upload a PDF and parse it.

        If background=True the task will be scheduled and a 202 returned
        with a "task_id". Otherwise the parsing will be done synchronously
        and the parsed document returned.
        """
        if file.content_type not in ("application/pdf",):
            raise HTTPException(status_code=400, detail="Only PDF uploads are accepted")

        tmp_dir = Path(tempfile.gettempdir()) / "piazzati_parsing"
        tmp_dir.mkdir(parents=True, exist_ok=True)

        dest = tmp_dir / f"upload_{file.filename}_{int(time.time())}.pdf"
        content = await file.read()
        dest.write_bytes(content)

        parser = get_parser()

        if background:
            # schedule
            task_id = str(uuid.uuid4())

            def _bg():
                try:
                    # Apri una sessione DB dedicata al task in background
                    db_bg = SessionLocal()
                    # Store initial status
                    _task_results[task_id] = {
                        "status": "processing",
                        "started_at": time.time(),
                        "filename": file.filename
                    }
                    
                    # run parser
                    doc = parser.parse(str(dest))
                    # attach optional metadata if provided
                    try:
                        if user_id:
                            doc.user_id = user_id
                        if Tags:
                            try:
                                doc.tags = json.loads(Tags)
                            except Exception:
                                # fallback: ignore malformed tags
                                pass
                    except Exception:
                        pass

                    # Save to batch processing storage
                    batch_storage = get_batch_storage()
                    json_path = batch_storage.save_parsed_cv(doc, file.filename)
                    print(f"📦 CV salvato per batch NLP: {json_path}")

                    # Salva anche nel DB come ultimo CV per l'utente (se presente)
                    if user_id:
                        _save_parsed_cv_to_db(db_bg, user_id, doc)

                    # Avvia pipeline batch (embeddings) per la data odierna
                    try:
                        process_date = datetime.now().strftime("%Y-%m-%d")
                        logger.info("Starting batch process from background job for date %s", process_date)
                        _start_batch_process(process_date)
                    except Exception as e:
                        logger.exception("Impossibile avviare batch automatico nel background: %s", str(e))

                    # Store successful result
                    parsed_data = (
                        doc.model_dump()
                        if hasattr(doc, "model_dump")
                        else getattr(doc, "dict", lambda: {})()
                    )
                    # Unifica nomenclatura: user_id canonico, id alias uguale
                    if isinstance(parsed_data, dict):
                        uid = parsed_data.get("user_id") or user_id
                        if uid:
                            parsed_data["user_id"] = uid
                            parsed_data["id"] = uid
                    _task_results[task_id] = {
                        "status": "completed",
                        "started_at": _task_results[task_id]["started_at"],
                        "completed_at": time.time(),
                        "filename": file.filename,
                        "result": jsonable_encoder(parsed_data),
                        "summary": display_parsing_results(doc)
                    }
                    
                    logger.info("Background parse finished: %s (user_id=%s)", task_id, getattr(doc, 'user_id', None))
                except Exception as e:
                    # Store error result
                    import traceback as _tb
                    _task_results[task_id] = {
                        "status": "failed",
                        "started_at": _task_results.get(task_id, {}).get("started_at", time.time()),
                        "failed_at": time.time(),
                        "filename": file.filename,
                        "error": str(e),
                        "traceback": _tb.format_exc()
                    }
                    logger.error("Background parse failed: %s - %s", task_id, str(e))
                finally:
                    try:
                        db_bg.close()
                    except Exception:
                        pass

            if background_tasks is None:
                raise HTTPException(
                    status_code=500,
                    detail="Background tasks unavailable",
                )

            background_tasks.add_task(_bg)
            return JSONResponse(status_code=202, content={"task_id": task_id})
        else:
            # Synchronous parsing path. Wrap in try/except to return
            # helpful traceback during local development.
            try:
                doc = parser.parse(str(dest))

                # attach optional metadata coming from the form
                if user_id:
                    try:
                        doc.user_id = user_id
                    except Exception:
                        pass

                if Tags:
                    try:
                        parsed_tags = json.loads(Tags)
                        if isinstance(parsed_tags, dict):
                            doc.tags = parsed_tags
                    except Exception:
                        # ignore malformed tags
                        pass

                # Save to batch processing storage
                batch_storage = get_batch_storage()
                json_path = batch_storage.save_parsed_cv(doc, file.filename)
                print(f"📦 CV salvato per batch NLP: {json_path}")

                # Salva anche nel DB come ultimo CV per l'utente (se presente)
                if user_id:
                    _save_parsed_cv_to_db(db, user_id, doc)

                # Schedule batch processing if possible
                try:
                    if background_tasks is not None:
                        process_date = datetime.now().strftime("%Y-%m-%d")
                        logger.info("Scheduling batch process for date %s (sync upload)", process_date)
                        background_tasks.add_task(_start_batch_process, process_date)
                except Exception as e:
                    logger.exception("Impossibile schedulare batch automatico (sync path): %s", str(e))

                text_summary = display_parsing_results(doc)
                parsed = (
                    doc.model_dump()
                    if hasattr(doc, "model_dump")
                    else getattr(doc, "dict", lambda: {})()
                )

                # Unifica nomenclatura: user_id canonico, id alias uguale
                if isinstance(parsed, dict):
                    uid = parsed.get("user_id") or user_id
                    if uid:
                        parsed["user_id"] = uid
                        parsed["id"] = uid

                # Ensure all values (e.g. datetimes) are JSON-serializable
                return JSONResponse(
                    status_code=200,
                    content={"parsed": jsonable_encoder(parsed), "summary": text_summary},
                )
            except Exception as e:
                # Development helper: include traceback in response body so the
                # frontend / curl can show the error without opening server logs.
                import traceback as _tb

                tb = _tb.format_exc()
                # Log to server console as well
                logger.exception("Synchronous parse failed: %s", str(e))
                return JSONResponse(
                    status_code=500,
                    content={"error": str(e), "traceback": tb},
                )
else:
    @router.post("/upload")
    async def upload_and_parse():
        # multipart not available in this environment (tests may run in a
        # minimal container). Return 501 to indicate the feature is missing.
        raise HTTPException(status_code=501, detail="multipart support not available")
