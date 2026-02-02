from sqlalchemy.orm import Session
from ..database import get_db
from ..models import Document


from fastapi import Depends, APIRouter, File, UploadFile, Form, HTTPException
router = APIRouter(prefix="/parse", tags=["parse"])

@router.post("/upload_db")
async def upload_and_save_cv(
    file: UploadFile = File(...),
    user_id: str = Form(...),
    background: bool = False,
    db: Session = Depends(get_db),
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
    parsed_json = doc_parsed.model_dump() if hasattr(doc_parsed, "model_dump") else getattr(doc_parsed, "dict", lambda: {{}})()

    # Sostituisci il vecchio CV (is_latest)
    from sqlalchemy import and_
    old_cv = db.query(Document).filter(and_(Document.user_id == user_id, Document.type == 'cv', Document.is_latest == True)).first()
    if old_cv:
        old_cv.is_latest = False
        db.add(old_cv)
        db.commit()

    # Crea nuovo documento
    new_doc = Document(
        id=uuid.uuid4(),
        user_id=user_id,
        type='cv',
        is_latest=True,
        parsed_json=parsed_json,
        created_at=datetime.utcnow(),
        updated_at=datetime.utcnow(),
        status='parsed',
    )
    db.add(new_doc)
    db.commit()
    db.refresh(new_doc)

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
import tempfile
import time
import uuid
from pathlib import Path

from ..parsers.ollama_cv_parser import OllamaCVParser
from ..utils.parsing_display import display_parsing_results
from ..services.cv_batch_storage import get_batch_storage
from fastapi import (
    APIRouter,
    BackgroundTasks,
    File,
    Form,
    HTTPException,
    UploadFile,
)
import json
import importlib.util
from fastapi.responses import JSONResponse
from fastapi.encoders import jsonable_encoder
from datetime import datetime

router = APIRouter(prefix="/parse", tags=["parse"])


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
    
    def _batch_processing():
        try:
            print(f"🚀 Avvio batch processing per data: {process_date}")
            
            # Import del batch processor
            import subprocess
            import sys
            
            # Path dello script batch processor
            script_path = Path(__file__).parent.parent.parent / "batch_processor.py"
            
            if not script_path.exists():
                raise FileNotFoundError(f"Batch processor script non trovato: {script_path}")
            
            # Esegui batch processing
            result = subprocess.run([
                sys.executable, str(script_path), 
                "--process-date", process_date
            ], capture_output=True, text=True, timeout=3600)  # 1 ora timeout
            
            if result.returncode == 0:
                print(f"✅ Batch processing completato per {process_date}")
                print(f"Output: {result.stdout}")
            else:
                print(f"❌ Batch processing fallito per {process_date}")
                print(f"Errore: {result.stderr}")
                
        except Exception as e:
            print(f"❌ Errore batch processing: {e}")
            import traceback
            traceback.print_exc()
    
    background_tasks.add_task(_batch_processing)
    
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

                    # Store successful result
                    parsed_data = (
                        doc.model_dump()
                        if hasattr(doc, "model_dump")
                        else getattr(doc, "dict", lambda: {})()
                    )

                    # Assicura che l'ID utente sia sempre presente nel JSON parsed
                    if user_id and isinstance(parsed_data, dict):
                        # Per retrocompatibilità manteniamo anche "id"
                        parsed_data["id"] = user_id
                        parsed_data["user_id"] = user_id
                    _task_results[task_id] = {
                        "status": "completed",
                        "started_at": _task_results[task_id]["started_at"],
                        "completed_at": time.time(),
                        "filename": file.filename,
                        "result": jsonable_encoder(parsed_data),
                        "summary": display_parsing_results(doc)
                    }
                    
                    print(f"Background parse finished: {task_id} (user_id={getattr(doc, 'user_id', None)})")
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
                    print(f"Background parse failed: {task_id} - {e}")

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

                text_summary = display_parsing_results(doc)
                parsed = (
                    doc.model_dump()
                    if hasattr(doc, "model_dump")
                    else getattr(doc, "dict", lambda: {})()
                )

                # Ensure all values (e.g. datetimes) are JSON-serializable
                # Assicura che l'ID utente sia sempre presente nei dati parsed
                if user_id and isinstance(parsed, dict):
                    # Per retrocompatibilità manteniamo anche "id"
                    parsed["id"] = user_id
                    parsed["user_id"] = user_id
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
                print("Synchronous parse failed:", str(e))
                print(tb)
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
