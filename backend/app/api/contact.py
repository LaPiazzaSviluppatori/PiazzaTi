from datetime import datetime
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from enum import Enum

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models.user import User
from ..models.document import Document

router = APIRouter()


class ContactCandidatePayload(BaseModel):
    jd_id: str
    candidate_id: str
    message: str
    origin: Optional[str] = None  # "spontaneous" | "top20" | altri in futuro


@router.post("/contact/candidate")
async def contact_candidate(
    payload: ContactCandidatePayload,
    current_user: Optional[User] = Depends(get_current_user),
):
    """Riceve un messaggio da un'azienda per un candidato specifico.

    Per ora il messaggio viene solo salvato in un file JSONL sul filesystem,
    così da non richiedere modifiche allo schema del database.
    """

    base_dir = Path("/app/data")
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        log_path = base_dir / "contact_messages.jsonl"

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "from_user_id": str(current_user.id) if current_user else None,
            "from_role": getattr(current_user, "role", None) if current_user else None,
            "from_company": getattr(current_user, "company", None) if current_user else None,
            "from_name": getattr(current_user, "name", None) if current_user else None,
            "origin": payload.origin,
            "jd_id": payload.jd_id,
            "candidate_id": payload.candidate_id,
            "message": payload.message,
        }

        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio messaggio: {e}")


class InboxMessage(BaseModel):
    id: str
    timestamp: str
    jd_id: str
    message: str
    from_company: Optional[str] = None
    from_name: Optional[str] = None
    origin: Optional[str] = None


class ConversationMessage(BaseModel):
    id: str
    timestamp: str
    jd_id: str
    candidate_id: str
    message: str
    from_role: Optional[str] = None
    from_company: Optional[str] = None
    from_name: Optional[str] = None


@router.get("/contact/inbox", response_model=List[InboxMessage])
async def get_inbox(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Restituisce tutti i messaggi ricevuti dal candidato corrente.

    I messaggi sono letti dal file JSONL e arricchiti con nome e company
    del mittente usando la tabella users.
    """

    base_dir = Path("/app/data")
    log_path = base_dir / "contact_messages.jsonl"

    if not log_path.exists():
        return []

    try:
        raw_entries: List[Dict[str, Any]] = []
        with log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    raw_entries.append(raw)
                except json.JSONDecodeError:
                    continue

        # Filtra per candidate_id == current_user.id e solo messaggi provenienti dall'azienda
        # (from_role == "company" o None per compatibilità con vecchi dati)
        cid = str(current_user.id)
        entries = [
            e
            for e in raw_entries
            if str(e.get("candidate_id")) == cid
            and (e.get("from_role") is None or str(e.get("from_role")) == "company")
        ]

        # Precarica mittenti dal DB
        sender_ids = {e.get("from_user_id") for e in entries if e.get("from_user_id")}
        senders: Dict[str, User] = {}
        if sender_ids:
            users = db.query(User).filter(User.id.in_(list(sender_ids))).all()
            for u in users:
                senders[str(u.id)] = u

        # Costruisci risposta ordinata per timestamp desc
        def parse_ts(ts: str) -> float:
            try:
                return datetime.fromisoformat(ts).timestamp()
            except Exception:
                return 0.0

        entries.sort(key=lambda e: parse_ts(str(e.get("timestamp", ""))), reverse=True)

        result: List[InboxMessage] = []
        for idx, e in enumerate(entries):
            from_user_id = str(e.get("from_user_id")) if e.get("from_user_id") else None
            sender = senders.get(from_user_id) if from_user_id else None
            msg = InboxMessage(
                id=f"{e.get('timestamp','')}:{idx}",
                timestamp=str(e.get("timestamp")),
                jd_id=str(e.get("jd_id")),
                message=str(e.get("message", "")),
                from_company=getattr(sender, "company", None) if sender else None,
                from_name=getattr(sender, "name", None) if sender else None,
                origin=str(e.get("origin")) if e.get("origin") is not None else None,
            )
            result.append(msg)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore lettura inbox: {e}")


@router.get("/contact/conversation", response_model=List[ConversationMessage])
async def get_conversation(
    jd_id: str,
    current_user: User = Depends(get_current_user),
):
    """Restituisce la conversazione completa per una coppia (candidate, JD).

    Usa lo stesso file JSONL dei messaggi di contatto e restituisce sia i
    messaggi inviati dall'azienda sia le eventuali risposte del candidato.
    """

    base_dir = Path("/app/data")
    log_path = base_dir / "contact_messages.jsonl"

    if not log_path.exists():
        return []

    try:
        raw_entries: List[Dict[str, Any]] = []
        with log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    raw_entries.append(raw)
                except json.JSONDecodeError:
                    continue

        cid = str(current_user.id)
        # Filtra tutti i messaggi per questo candidato e JD
        entries = [
            e
            for e in raw_entries
            if str(e.get("candidate_id")) == cid and str(e.get("jd_id")) == jd_id
        ]

        def parse_ts(ts: str) -> float:
            try:
                return datetime.fromisoformat(ts).timestamp()
            except Exception:
                return 0.0

        # Ordine cronologico crescente per visualizzazione stile chat
        entries.sort(key=lambda e: parse_ts(str(e.get("timestamp", ""))))

        result: List[ConversationMessage] = []
        for idx, e in enumerate(entries):
            msg = ConversationMessage(
                id=f"{e.get('timestamp','')}:{idx}",
                timestamp=str(e.get("timestamp")),
                jd_id=str(e.get("jd_id")),
                candidate_id=str(e.get("candidate_id")),
                message=str(e.get("message", "")),
                from_role=str(e.get("from_role")) if e.get("from_role") is not None else None,
                from_company=str(e.get("from_company")) if e.get("from_company") is not None else None,
                from_name=str(e.get("from_name")) if e.get("from_name") is not None else None,
            )
            result.append(msg)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore lettura conversazione: {e}")


class ApplyPayload(BaseModel):
    jd_id: str
    message: Optional[str] = None


@router.post("/contact/apply")
async def apply_to_jd(
    payload: ApplyPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Permette a un candidato di candidarsi a una JD.

    Salva l'applicazione in un file JSONL (applications.jsonl) con info su
    candidato, JD e azienda destinataria.
    """

    if current_user.role != "candidate":
        raise HTTPException(status_code=403, detail="Solo i candidati possono candidarsi alle JD")

    base_dir = Path("/app/data")
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        log_path = base_dir / "applications.jsonl"

        # Recupera info JD e azienda associata
        company_name: Optional[str] = None
        try:
            jd = db.query(Document).filter(Document.id == payload.jd_id).first()
            if jd is not None:
                if jd.parsed_json and isinstance(jd.parsed_json, dict):
                    company_name = jd.parsed_json.get("company") or company_name
                if not company_name:
                    company_name = jd.title
        except Exception:
            # Se qualcosa va storto col DB, continuiamo comunque salvando la candidatura
            pass

        entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "candidate_user_id": str(current_user.id),
            "candidate_name": getattr(current_user, "name", None),
            "candidate_email": getattr(current_user, "email", None),
            "jd_id": payload.jd_id,
            "company": company_name,
            "message": payload.message or "",
        }

        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio candidatura: {e}")


class CompanyApplication(BaseModel):
    id: str
    timestamp: str
    jd_id: str
    candidate_user_id: str
    candidate_name: Optional[str] = None
    candidate_email: Optional[str] = None
    message: str
    company: Optional[str] = None


@router.get("/contact/applications", response_model=List[CompanyApplication])
async def get_applications(
    current_user: User = Depends(get_current_user),
):
    """Restituisce le candidature ricevute per le JD dell'azienda corrente."""

    if current_user.role != "company":
        raise HTTPException(status_code=403, detail="Solo le aziende possono vedere le candidature ricevute")

    base_dir = Path("/app/data")
    log_path = base_dir / "applications.jsonl"

    if not log_path.exists():
        return []

    try:
        raw_entries: List[Dict[str, Any]] = []
        with log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    raw_entries.append(raw)
                except json.JSONDecodeError:
                    continue

        company_name = getattr(current_user, "company", None)
        if company_name:
            entries = [e for e in raw_entries if str(e.get("company")) == company_name]
        else:
            entries = []

        def parse_ts(ts: str) -> float:
            try:
                return datetime.fromisoformat(ts).timestamp()
            except Exception:
                return 0.0

        entries.sort(key=lambda e: parse_ts(str(e.get("timestamp", ""))), reverse=True)

        result: List[CompanyApplication] = []
        for idx, e in enumerate(entries):
            app = CompanyApplication(
                id=f"{e.get('timestamp','')}:{idx}",
                timestamp=str(e.get("timestamp")),
                jd_id=str(e.get("jd_id")),
                candidate_user_id=str(e.get("candidate_user_id")),
                candidate_name=str(e.get("candidate_name")) if e.get("candidate_name") is not None else None,
                candidate_email=str(e.get("candidate_email")) if e.get("candidate_email") is not None else None,
                message=str(e.get("message", "")),
                company=str(e.get("company")) if e.get("company") is not None else None,
            )
            result.append(app)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore lettura candidature: {e}")


class CandidateApplication(BaseModel):
    id: str
    timestamp: str
    jd_id: str
    company: Optional[str] = None
    message: str


@router.get("/contact/my_applications", response_model=List[CandidateApplication])
async def get_my_applications(
    current_user: User = Depends(get_current_user),
):
    """Restituisce le candidature spontanee inviate dal candidato corrente.

    Usa lo stesso file JSONL delle candidature lato azienda ma filtrando per
    candidate_user_id == utente loggato.
    """

    if current_user.role != "candidate":
        raise HTTPException(status_code=403, detail="Solo i candidati possono vedere le proprie candidature")

    base_dir = Path("/app/data")
    log_path = base_dir / "applications.jsonl"

    if not log_path.exists():
        return []

    try:
        raw_entries: List[Dict[str, Any]] = []
        with log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    raw_entries.append(raw)
                except json.JSONDecodeError:
                    continue

        cid = str(current_user.id)
        entries = [e for e in raw_entries if str(e.get("candidate_user_id")) == cid]

        def parse_ts(ts: str) -> float:
            try:
                return datetime.fromisoformat(ts).timestamp()
            except Exception:
                return 0.0

        entries.sort(key=lambda e: parse_ts(str(e.get("timestamp", ""))), reverse=True)

        result: List[CandidateApplication] = []
        for idx, e in enumerate(entries):
            app = CandidateApplication(
                id=f"{e.get('timestamp','')}:{idx}",
                timestamp=str(e.get("timestamp")),
                jd_id=str(e.get("jd_id")),
                company=str(e.get("company")) if e.get("company") is not None else None,
                message=str(e.get("message", "")),
            )
            result.append(app)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore lettura candidature candidato: {e}")


class FeedbackType(str, Enum):
    POSITIVE = "positive"
    CONSTRUCTIVE = "constructive"
    NEUTRAL = "neutral"


class SendFeedbackPayload(BaseModel):
    jd_id: str
    candidate_id: str
    type: FeedbackType
    message: Optional[str] = None


class CandidateFeedback(BaseModel):
    id: str
    timestamp: str
    jd_id: str
    jd_title: Optional[str] = None
    company: Optional[str] = None
    type: FeedbackType
    message: str


@router.post("/contact/feedback")
async def send_feedback(
    payload: SendFeedbackPayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Consente all'azienda di inviare un feedback finale su un candidato per una JD.

    Il feedback viene salvato in un file JSONL dedicato (feedback.jsonl) e conterrà
    tipo (positive/constructive/neutral), messaggio opzionale, titolo JD e nome azienda.
    """

    if current_user.role != "company":
        raise HTTPException(status_code=403, detail="Solo le aziende possono inviare feedback")

    base_dir = Path("/app/data")
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        log_path = base_dir / "feedback.jsonl"

        jd_title: Optional[str] = None
        company_name: Optional[str] = getattr(current_user, "company", None)

        # Recupera informazioni sulla JD per arricchire il feedback
        try:
            jd = db.query(Document).filter(Document.id == payload.jd_id).first()
            if jd is not None:
                if jd.parsed_json and isinstance(jd.parsed_json, dict):
                    jd_title = jd.parsed_json.get("title") or jd_title
                    company_name = jd.parsed_json.get("company") or company_name
                if not jd_title:
                    jd_title = jd.title
        except Exception:
            # Se qualcosa va storto col DB, continuiamo comunque salvando il feedback
            pass

        entry: Dict[str, Any] = {
            "timestamp": datetime.utcnow().isoformat(),
            "from_user_id": str(current_user.id),
            "from_company": getattr(current_user, "company", None),
            "from_name": getattr(current_user, "name", None),
            "candidate_id": str(payload.candidate_id),
            "jd_id": payload.jd_id,
            "jd_title": jd_title,
            "company": company_name,
            "type": payload.type.value,
            "message": payload.message or "",
        }

        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio feedback: {e}")


@router.get("/contact/feedback/my", response_model=List[CandidateFeedback])
async def get_my_feedback(
    current_user: User = Depends(get_current_user),
):
    """Restituisce tutti i feedback ricevuti dal candidato corrente.

    I feedback sono letti dal file JSONL dedicato e ordinati per timestamp decrescente.
    """

    if current_user.role != "candidate":
        raise HTTPException(status_code=403, detail="Solo i candidati possono vedere i propri feedback")

    base_dir = Path("/app/data")
    log_path = base_dir / "feedback.jsonl"

    if not log_path.exists():
        return []

    try:
        raw_entries: List[Dict[str, Any]] = []
        with log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    raw_entries.append(raw)
                except json.JSONDecodeError:
                    continue

        cid = str(current_user.id)
        entries = [e for e in raw_entries if str(e.get("candidate_id")) == cid]

        def parse_ts(ts: str) -> float:
            try:
                return datetime.fromisoformat(ts).timestamp()
            except Exception:
                return 0.0

        entries.sort(key=lambda e: parse_ts(str(e.get("timestamp", ""))), reverse=True)

        result: List[CandidateFeedback] = []
        for idx, e in enumerate(entries):
            fb = CandidateFeedback(
                id=f"{e.get('timestamp','')}:{idx}",
                timestamp=str(e.get("timestamp")),
                jd_id=str(e.get("jd_id")),
                jd_title=str(e.get("jd_title")) if e.get("jd_title") is not None else None,
                company=str(e.get("company")) if e.get("company") is not None else None,
                type=FeedbackType(str(e.get("type", "neutral"))),
                message=str(e.get("message", "")),
            )
            result.append(fb)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore lettura feedback: {e}")


class ConversationReplyPayload(BaseModel):
    jd_id: str
    message: str


@router.post("/contact/reply")
async def reply_to_contact(
    payload: ConversationReplyPayload,
    current_user: User = Depends(get_current_user),
):
    """Permette al candidato (e in futuro all'azienda) di rispondere in chat.

    Le risposte vengono salvate nello stesso file JSONL usato per i messaggi
    iniziali di contatto, così la conversazione può essere ricostruita
    interamente dal frontend.
    """

    base_dir = Path("/app/data")
    try:
        base_dir.mkdir(parents=True, exist_ok=True)
        log_path = base_dir / "contact_messages.jsonl"

        entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "from_user_id": str(current_user.id),
            "from_role": getattr(current_user, "role", None),
            "from_company": getattr(current_user, "company", None),
            "from_name": getattr(current_user, "name", None),
            # Per ora supportiamo solo risposte del candidato, quindi candidate_id = current_user.id
            "candidate_id": str(current_user.id),
            "jd_id": payload.jd_id,
            "message": payload.message,
        }

        with log_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")

        return {"status": "ok"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore salvataggio risposta: {e}")


@router.get("/contact/conversation/company", response_model=List[ConversationMessage])
async def get_conversation_company(
    jd_id: str,
    candidate_id: str,
    current_user: User = Depends(get_current_user),
):
    """Restituisce la conversazione per una JD e un candidato, vista lato azienda.

    Per sicurezza verifica che l'azienda corrente sia effettivamente destinataria
    della candidatura (applications.jsonl) prima di mostrare i messaggi.
    """

    if current_user.role != "company":
        raise HTTPException(status_code=403, detail="Solo le aziende possono vedere questa conversazione")

    base_dir = Path("/app/data")
    apps_path = base_dir / "applications.jsonl"
    log_path = base_dir / "contact_messages.jsonl"

    # Se non esiste il file delle candidature o dei messaggi, restituisci lista vuota
    if not log_path.exists():
        return []

    # Verifica che esista almeno una candidatura per questa combinazione
    if apps_path.exists():
        try:
            has_application = False
            with apps_path.open("r", encoding="utf-8") as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        raw = json.loads(line)
                    except json.JSONDecodeError:
                        continue
                    if (
                        str(raw.get("candidate_user_id")) == str(candidate_id)
                        and str(raw.get("jd_id")) == str(jd_id)
                        and str(raw.get("company")) == getattr(current_user, "company", None)
                    ):
                        has_application = True
                        break
            if not has_application:
                raise HTTPException(status_code=403, detail="Conversazione non autorizzata per questa azienda")
        except HTTPException:
            raise
        except Exception as e:
            raise HTTPException(status_code=500, detail=f"Errore verifica candidatura: {e}")

    try:
        raw_entries: List[Dict[str, Any]] = []
        with log_path.open("r", encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    raw = json.loads(line)
                    raw_entries.append(raw)
                except json.JSONDecodeError:
                    continue

        # Filtra tutti i messaggi per questo candidato e JD
        cid = str(candidate_id)
        entries = [
            e
            for e in raw_entries
            if str(e.get("candidate_id")) == cid and str(e.get("jd_id")) == jd_id
        ]

        def parse_ts(ts: str) -> float:
            try:
                return datetime.fromisoformat(ts).timestamp()
            except Exception:
                return 0.0

        entries.sort(key=lambda e: parse_ts(str(e.get("timestamp", ""))))

        result: List[ConversationMessage] = []
        for idx, e in enumerate(entries):
            msg = ConversationMessage(
                id=f"{e.get('timestamp','')}:{idx}",
                timestamp=str(e.get("timestamp")),
                jd_id=str(e.get("jd_id")),
                candidate_id=str(e.get("candidate_id")),
                message=str(e.get("message", "")),
                from_role=str(e.get("from_role")) if e.get("from_role") is not None else None,
                from_company=str(e.get("from_company")) if e.get("from_company") is not None else None,
                from_name=str(e.get("from_name")) if e.get("from_name") is not None else None,
            )
            result.append(msg)

        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore lettura conversazione azienda: {e}")
