import os
from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

router = APIRouter()

# Integrazione matcher basato su NLP/single_match.py
# Possiamo usarlo come servizio HTTP esterno (legacy) oppure
# richiamare direttamente la funzione Python compare_cv_with_jd.

try:
    # Import diretto dal modulo NLP (stesso repo)
    from NLP.single_match import compare_cv_with_jd  # type: ignore
except Exception:  # pragma: no cover - dipende dal PYTHONPATH
    compare_cv_with_jd = None  # type: ignore


class MatchRequest(BaseModel):
    cv_path: str  # in pratica user_id del candidato
    jd_path: str  # jd_id della job description


@router.post("/match_cv_jd")
async def proxy_match_cv_jd(request: MatchRequest):
    """Esegue il match CV↔JD usando direttamente la logica NLP/single_match.

    Riceve dal frontend cv_path/jd_path che corrispondono a
    user_id/jd_id presenti nei dataset del matcher.
    """
    if compare_cv_with_jd is None:
        # Import fallito: ambiente non configurato correttamente
        raise HTTPException(
            status_code=500,
            detail=(
                "Matcher interno non disponibile: impossibile importare NLP.single_match. "
                "Verifica Python path e presenza della cartella NLP nel container backend."
            ),
        )

    try:
        # Chiamata diretta alla funzione principale del matcher
        result = compare_cv_with_jd(user_id=request.cv_path, jd_id=request.jd_path)
        return result
    except ValueError as e:
        # Errori noti di validazione (ID non presenti nei dataset del matcher)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # Propaga altri errori interni come 502 per distinguere dai casi di input non valido
        raise HTTPException(status_code=502, detail=f"Matcher internal error: {str(e)}")


@router.get("/match_cv_jd")
async def proxy_match_cv_jd_get(user_id: str = Query(...), jd_id: str = Query(...)):
    """Compatibilità GET per chiamate dirette (es. curl). Usa gli stessi parametri del POST.

    Esegue il match CV↔JD usando `user_id` e `jd_id` passati come query params.
    """
    if compare_cv_with_jd is None:
        raise HTTPException(
            status_code=500,
            detail=(
                "Matcher interno non disponibile: impossibile importare NLP.single_match. "
                "Verifica Python path e presenza della cartella NLP nel container backend."
            ),
        )

    try:
        result = compare_cv_with_jd(user_id=user_id, jd_id=jd_id)
        return result
    except ValueError as e:
        # Errori noti di validazione (ID non presenti nei dataset del matcher)
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # Propaga altri errori interni come 502 per distinguere dai casi di input non valido
        raise HTTPException(status_code=502, detail=f"Matcher internal error: {str(e)}")
