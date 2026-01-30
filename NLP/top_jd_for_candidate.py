import json
from pathlib import Path
import jwt  # pip install pyjwt

# Config
MATCH_RESULTS_PATH = Path(__file__).parent / "match_results" / "jd_cv_matches.json"
JWT_PATH = Path(__file__).parent / "user_jwt.txt"  # Puoi salvare qui il token dopo login
TOP_N = 20

def get_user_id_from_jwt(token: str) -> str:
    payload = jwt.decode(token, options={"verify_signature": False})
    return payload["sub"]

def get_top_jd_for_candidate(user_id: str, top_n: int = 20):
    with open(MATCH_RESULTS_PATH, "r", encoding="utf-8") as f:
        data = json.load(f)
    results = []
    for jd_id, jd_info in data["matches"].items():
        for candidate in jd_info["candidates"]:
            if candidate["user_id"] == user_id:
                results.append({
                    "jd_id": jd_id,
                    "title": jd_info["title"],
                    "score": candidate["score"],
                    "rank": candidate["rank"],
                    "preview": candidate["preview"]
                })
    # Ordina per score decrescente e prendi i primi top_n
    results.sort(key=lambda x: x["score"], reverse=True)
    return results[:top_n]

if __name__ == "__main__":
    # Leggi il JWT da file (o da input)
    try:
        with open(JWT_PATH, "r", encoding="utf-8") as f:
            jwt_token = f.read().strip()
        user_id = get_user_id_from_jwt(jwt_token)
    except Exception as e:
        print("Errore nel recupero JWT o user_id:", e)
        exit(1)
    top_jds = get_top_jd_for_candidate(user_id, TOP_N)
    print(f"Top {TOP_N} JD per candidato {user_id}:")
    if not top_jds:
        print("Nessun match trovato.")
    for jd in top_jds:
        print(f"JD: {jd['title']} | Score: {jd['score']:.3f} | Rank: {jd['rank']} | Preview: {jd['preview'][:80]}...")
