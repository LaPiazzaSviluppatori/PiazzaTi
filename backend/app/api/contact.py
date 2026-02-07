from datetime import datetime
import json
from pathlib import Path
from typing import Optional, List, Dict, Any

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..auth import get_current_user, get_db
from ..models.user import User

router = APIRouter()


class ContactCandidatePayload(BaseModel):
    jd_id: str
    candidate_id: str
    message: str


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

        # Filtra per candidate_id == current_user.id
        cid = str(current_user.id)
        entries = [e for e in raw_entries if str(e.get("candidate_id")) == cid]

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
            )
            result.append(msg)

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Errore lettura inbox: {e}")
