from fastapi import FastAPI, Query, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import uvicorn

"""
User CV Matcher - Confronto singolo CV con JD
Usa la stessa pipeline del reranker aziendale.

AGGIORNAMENTO v1.3.0:
- Integrazione XAI inline (spiegazioni automatiche)
- Aggiunto campo 'xai' nell'output con top_reasons, main_risks, evidence
- Aggiunto seniority_details, skills_details, experience_details
"""

import json
import re
import warnings
import difflib
from pathlib import Path
from typing import Dict, Set, Tuple, Optional, List, Any
from datetime import datetime
from dataclasses import dataclass, field
import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')


# ============================================================================
# CONFIGURAZIONE
# ============================================================================

@dataclass
class Config:
    """Configurazione per il matcher"""
    BASE_DIR: Path = Path(__file__).parent.resolve()
    EMBEDDINGS_DIR: Path = BASE_DIR / "embeddings"
    CV_EMBEDDINGS_FILE: str = "cv_embeddings.csv"
    JD_EMBEDDINGS_FILE: str = "jd_embeddings.csv"
    CV_DATASET_PATH: Path = BASE_DIR / "Dataset/normalized/cv_dataset_normalized.csv"
    JD_DATASET_PATH: Path = BASE_DIR / "Dataset/normalized/jd_dataset_normalized.csv"

    QUALITY_THRESHOLDS: Dict[str, float] = field(default_factory=lambda: {
        'excellent': 0.5, 'good': 0.3, 'weak': 0.0
    })
    
    SENIORITY_LEVELS: Dict[str, int] = field(default_factory=lambda: {
        'junior': 1, 'mid': 2, 'senior': 3
    })
    
    WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        # Pesi v1.2 (×1.5 per migliore differenziazione)
        'cosine_similarity_normalized': 0.45,
        'skill_overlap_core_norm': 0.30,
        'skill_coverage_total': 0.15,
        'skill_overlap_nice_norm': 0.075,
        'experience_meets_requirement': 0.30,
        'seniority_match': 0.075,
        'role_similarity_jaccard': 0.10,
        'role_coherent': 0.10,
        'must_have_missing': -0.075,
        'experience_penalty_soft': -0.15,
        'seniority_mismatch_strong': -0.225,
        'seniority_underskilled': -0.075,
    })
    
    EXPERIENCE_GAP_PENALTY_FACTOR: float = 0.1
    DEI_TAG_BOOST: float = 0.05


# ============================================================================
# XAI CONFIGURATION & TEMPLATES
# ============================================================================

@dataclass
class XAIThresholds:
    """Soglie per la generazione delle spiegazioni XAI - calibrate per pesi v1.2"""
    COSINE_STRONG: float = 0.65
    COSINE_MODERATE: float = 0.45
    SKILL_CORE_STRONG: float = 0.6
    SKILL_CORE_PARTIAL: float = 0.2
    SKILL_NICE_THRESHOLD: float = 0.25
    ROLE_SIMILARITY_MIN: float = 0.2
    MISSING_SKILLS_HIGH: int = 2
    EXPERIENCE_GAP_HIGH: float = 1.5


DEFAULT_XAI_THRESHOLDS = XAIThresholds()

# Template testuali per le spiegazioni (italiano)
REASON_TEMPLATES = {
    "semantic_match_strong": "Il profilo complessivo è fortemente allineato con la posizione",
    "semantic_match_moderate": "Il profilo mostra buon allineamento con la posizione",
    "core_skills_strong": "Possiede la maggior parte delle competenze core richieste",
    "core_skills_partial": "Possiede alcune delle competenze core richieste",
    "nice_skills_present": "Ha competenze aggiuntive desiderate (nice-to-have)",
    "experience_sufficient": "L'esperienza soddisfa i requisiti minimi",
    "experience_exceeds": "L'esperienza supera i requisiti richiesti",
    "seniority_aligned": "Il livello di seniority corrisponde alla posizione",
    "seniority_higher": "Ha seniority superiore a quella richiesta",
    "role_aligned": "Il ruolo attuale è coerente con la posizione",
}

RISK_TEMPLATES = {
    "missing_core_skills_high": "Mancano diverse competenze core richieste",
    "missing_core_skills_medium": "Mancano alcune competenze core richieste",
    "experience_below_critical": "Esperienza significativamente sotto il requisito minimo",
    "experience_below_minor": "Esperienza leggermente sotto il requisito minimo",
    "seniority_gap_critical": "Differenza di seniority significativa (≥2 livelli)",
    "underskilled": "Seniority inferiore a quella richiesta",
}


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def load_embeddings(csv_path: Path) -> Tuple[pd.DataFrame, Dict[str, np.ndarray]]:
    """Carica embeddings da CSV"""
    df = pd.read_csv(csv_path)
    id_col = 'user_id' if 'user_id' in df.columns else 'jd_id'

    # Ensure IDs are strings to avoid mismatches between int/str during lookup
    try:
        df[id_col] = df[id_col].astype(str)
    except Exception:
        df[id_col] = df[id_col].apply(lambda x: '' if pd.isna(x) else str(x))

    embeddings_dict = {}
    for _, row in df.iterrows():
        entity_id = str(row[id_col])
        embedding = np.array(json.loads(row['embedding_vector']))
        embeddings_dict[entity_id] = embedding
    return df, embeddings_dict


def load_normalized_datasets(config: Config) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Carica dataset normalizzati CV e JD"""
    cv_data = pd.read_csv(config.CV_DATASET_PATH)
    jd_data = pd.read_csv(config.JD_DATASET_PATH)

    # Ensure identifier columns are strings to match embeddings keys
    if 'user_id' in cv_data.columns:
        try:
            cv_data['user_id'] = cv_data['user_id'].astype(str)
        except Exception:
            cv_data['user_id'] = cv_data['user_id'].apply(lambda x: '' if pd.isna(x) else str(x))

    if 'jd_id' in jd_data.columns:
        try:
            jd_data['jd_id'] = jd_data['jd_id'].astype(str)
        except Exception:
            jd_data['jd_id'] = jd_data['jd_id'].apply(lambda x: '' if pd.isna(x) else str(x))

    return cv_data, jd_data


def load_all_data(config: Config) -> dict:
    """Carica tutti i dati necessari: embeddings + dataset"""
    cv_emb_path = config.EMBEDDINGS_DIR / config.CV_EMBEDDINGS_FILE
    jd_emb_path = config.EMBEDDINGS_DIR / config.JD_EMBEDDINGS_FILE

    cv_emb_df, cv_embeddings = load_embeddings(cv_emb_path)
    jd_emb_df, jd_embeddings = load_embeddings(jd_emb_path)

    cv_data, jd_data = load_normalized_datasets(config)

    return {
        'cv_emb_df': cv_emb_df, 'cv_embeddings': cv_embeddings,
        'jd_emb_df': jd_emb_df, 'jd_embeddings': jd_embeddings,
        'cv_data': cv_data, 'jd_data': jd_data
    }


def cosine_similarity(vec1: np.ndarray, vec2: np.ndarray) -> float:
    """Calcola similarità coseno tra due vettori"""
    norm1 = np.linalg.norm(vec1)
    norm2 = np.linalg.norm(vec2)
    if norm1 == 0 or norm2 == 0:
        return 0.0
    return float(np.dot(vec1, vec2) / (norm1 * norm2))


def get_quality_label(score: float, config: Config) -> str:
    """Assegna etichetta di qualità in base al score"""
    if score >= config.QUALITY_THRESHOLDS['excellent']:
        return 'EXCELLENT'
    elif score >= config.QUALITY_THRESHOLDS['good']:
        return 'GOOD'
    return 'WEAK'


def parse_skills_string(skills_str: str) -> Set[str]:
    """Parsa stringa skills (comma-separated) in set"""
    if pd.isna(skills_str) or skills_str == '':
        return set()
    skills = set()
    for skill in str(skills_str).split(','):
        clean = skill.strip().lower()
        clean = re.sub(r'^[\*e\s]+', '', clean)
        if clean:
            skills.add(clean)
    return skills


def extract_years_from_requirements_legacy(req_str: str) -> Optional[int]:
    """LEGACY: Estrae anni di esperienza richiesti dalla stringa requirements."""
    if pd.isna(req_str):
        return None
    patterns = [r'(\d+)\+?\s*years?', r'(\d+)\+?\s*anni']
    for pattern in patterns:
        match = re.search(pattern, str(req_str).lower())
        if match:
            return int(match.group(1))
    return None


def get_seniority_numeric(seniority: str, config: Config) -> int:
    """Converte seniority string in valore numerico"""
    if pd.isna(seniority):
        return 0
    return config.SENIORITY_LEVELS.get(str(seniority).lower(), 0)


def get_seniority_string(seniority: str) -> str:
    """Normalizza e restituisce la stringa della seniority."""
    if pd.isna(seniority) or seniority == '':
        return 'unknown'
    return str(seniority).lower().strip()


def extract_current_role(experience_str: str) -> str:
    """Estrae il ruolo corrente da stringa esperienza"""
    if pd.isna(experience_str) or experience_str == '':
        return ''
    match = re.match(r'^([^@]+)\s*@', str(experience_str))
    return match.group(1).strip().lower() if match else ''


def compute_role_similarity(cv_role: str, jd_title: str) -> Tuple[float, int]:
    """Calcola similarità Jaccard tra ruolo CV e titolo JD"""
    if not cv_role or not jd_title:
        return 0.0, 0

    cv_tokens = set(re.findall(r'\w+', cv_role.lower()))
    jd_tokens = set(re.findall(r'\w+', jd_title.lower()))
    stopwords = {'a', 'an', 'the', 'of', 'in', 'at', 'for', 'and', 'or', 'di', 'e', 'il', 'la'}
    cv_tokens -= stopwords
    jd_tokens -= stopwords

    if not cv_tokens or not jd_tokens:
        return 0.0, 0

    intersection = len(cv_tokens & jd_tokens)
    union = len(cv_tokens | jd_tokens)
    jaccard = intersection / union if union > 0 else 0.0
    return jaccard, 1 if intersection > 0 else 0


# ============================================================================
# FEATURE ENGINEERING
# ============================================================================

def compute_features(user_id: str, jd_id: str, cosine_sim: float,
                     cv_data: pd.DataFrame, jd_data: pd.DataFrame, config: Config) -> Dict:
    """Calcola tutte le feature per una coppia (CV, JD)."""
    cv_row = cv_data[cv_data['user_id'] == user_id].iloc[0]
    jd_row = jd_data[jd_data['jd_id'] == jd_id].iloc[0]
    features = {}

    # ---- SEMANTIC SIMILARITY ----
    features['cosine_similarity_raw'] = cosine_sim
    features['cosine_similarity_normalized'] = cosine_sim

    # ---- SKILLS ANALYSIS ----
    cv_skills = parse_skills_string(cv_row.get('skills_normalized', ''))
    jd_req = parse_skills_string(jd_row.get('requirements_normalized', ''))
    jd_nice = parse_skills_string(jd_row.get('nice_to_have_normalized', ''))
    jd_req = {s for s in jd_req if not re.search(r'\d+\+?\s*(years?|anni)', s)}

    core_overlap = cv_skills & jd_req
    nice_overlap = cv_skills & jd_nice
    all_jd = jd_req | jd_nice
    all_overlap = cv_skills & all_jd

    jd_requirements_count = len(jd_req)
    jd_nice_to_have_count = len(jd_nice)

    features['skill_overlap_core_abs'] = len(core_overlap)
    features['jd_requirements_count'] = jd_requirements_count
    features['skill_overlap_core_norm'] = len(core_overlap) / jd_requirements_count if jd_requirements_count else 0.0
    features['skill_overlap_nice_abs'] = len(nice_overlap)
    features['jd_nice_to_have_count'] = jd_nice_to_have_count
    features['skill_overlap_nice_norm'] = len(nice_overlap) / jd_nice_to_have_count if jd_nice_to_have_count else 0.0
    features['skill_coverage_total'] = len(all_overlap) / len(all_jd) if all_jd else 0.0
    features['must_have_missing'] = jd_requirements_count - len(core_overlap)
    features['_cv_skills'] = list(cv_skills)
    features['_jd_requirements'] = list(jd_req)
    features['_jd_nice_to_have'] = list(jd_nice)
    features['_skills_matched'] = list(core_overlap)
    features['_skills_nice_matched'] = list(nice_overlap)

    # ---- EXPERIENCE ANALYSIS ----
    cv_years = cv_row.get('years_of_experience', 0)
    cv_years = 0 if pd.isna(cv_years) else float(cv_years)

    if 'min_experience_years_normalized' in jd_row.index:
        jd_years = jd_row.get('min_experience_years_normalized', 0)
    elif 'min_experience_years' in jd_row.index:
        jd_years = jd_row.get('min_experience_years', 0)
    else:
        jd_years = extract_years_from_requirements_legacy(jd_row.get('requirements', ''))
        
    jd_years = 0 if pd.isna(jd_years) else float(jd_years)
    gap = cv_years - jd_years

    features['years_experience_cv'] = cv_years
    features['years_required_jd'] = jd_years
    features['experience_gap'] = gap
    features['experience_gap_abs'] = abs(gap)
    features['experience_meets_requirement'] = 1 if cv_years >= jd_years else 0
    features['experience_penalty_soft'] = abs(gap) * config.EXPERIENCE_GAP_PENALTY_FACTOR if gap < 0 else 0.0

    # ---- SENIORITY ANALYSIS ----
    cv_sen = cv_row.get('inferred_seniority', '')
    jd_sen = jd_row.get('constraints_seniority_normalized', '')
    cv_level = get_seniority_numeric(cv_sen, config)
    jd_level = get_seniority_numeric(jd_sen, config)
    sen_gap = cv_level - jd_level

    features['seniority_cv_str'] = get_seniority_string(cv_sen)
    features['seniority_jd_str'] = get_seniority_string(jd_sen)
    features['seniority_cv'] = str(cv_sen) if pd.notna(cv_sen) else ''
    features['seniority_jd'] = str(jd_sen) if pd.notna(jd_sen) else ''
    features['seniority_cv_level'] = cv_level
    features['seniority_jd_level'] = jd_level
    features['seniority_gap'] = sen_gap
    features['seniority_match'] = 1 if cv_level == jd_level else 0
    features['seniority_mismatch_strong'] = 1 if abs(sen_gap) >= 2 else 0
    features['seniority_underskilled'] = 1 if cv_level < jd_level else 0

    # ---- ROLE ANALYSIS ----
    cv_role = extract_current_role(cv_row.get('experience', ''))
    jd_title = jd_row.get('title', '')
    role_sim, role_match = compute_role_similarity(cv_role, jd_title)

    features['cv_current_role'] = cv_role
    features['jd_title'] = jd_title
    features['role_similarity_jaccard'] = role_sim
    features['role_token_match'] = role_match
    features['role_coherent'] = 1 if role_sim > 0.2 else 0

    # ---- PARSING QUALITY ----
    has_summary = 1 if pd.notna(cv_row.get('summary', '')) and cv_row.get('summary', '') else 0
    has_exp = 1 if pd.notna(cv_row.get('experience', '')) and cv_row.get('experience', '') else 0
    has_edu = 1 if pd.notna(cv_row.get('education', '')) and cv_row.get('education', '') else 0
    has_skills = 1 if pd.notna(cv_row.get('skills_normalized', '')) and cv_row.get('skills_normalized', '') else 0
    has_lang = 1 if pd.notna(cv_row.get('languages_normalized', '')) and cv_row.get('languages_normalized', '') else 0
    sections = [has_summary, has_exp, has_edu, has_skills, has_lang]

    features['cv_has_summary'] = has_summary
    features['cv_has_experience'] = has_exp
    features['cv_has_education'] = has_edu
    features['cv_has_skills'] = has_skills
    features['cv_has_languages'] = has_lang
    features['cv_completeness_score'] = sum(sections) / len(sections)
    features['cv_skills_count'] = len(cv_skills)

    # ---- DEI TAGS ----
    tag_w = cv_row.get('tag_women', False)
    tag_p = cv_row.get('tag_protected_category', False)
    features['tag_women'] = 1 if pd.notna(tag_w) and tag_w else 0
    features['tag_protected_category'] = 1 if pd.notna(tag_p) and tag_p else 0
    features['dei_tag_count'] = features['tag_women'] + features['tag_protected_category']
    features['dei_boost'] = features['dei_tag_count'] * config.DEI_TAG_BOOST

    return features


# ============================================================================
# SCORING
# ============================================================================

def compute_score(features: Dict, config: Config) -> Dict:
    """Calcola score finale usando weighted linear combination."""
    score = 0.0
    contributions = {}

    for feat, weight in config.WEIGHTS.items():
        val = features.get(feat, 0)
        val = 0 if pd.isna(val) else val
        contrib = weight * val
        contributions[feat] = round(contrib, 4)
        score += contrib

    dei_boost = features.get('dei_boost', 0)
    final = max(0, min(1, score + dei_boost))

    return {
        'linear_score_raw': round(score, 4),
        'linear_score_normalized': round(score, 4),
        'dei_boost': round(dei_boost, 4),
        'final_score': round(final, 4),
        'contributions': contributions
    }


# ============================================================================
# XAI FUNCTIONS
# ============================================================================

def build_top_reasons(
    feature_values: Dict[str, float],
    feature_contributions: Dict[str, float],
    experience_details: Dict[str, Any],
    seniority_details: Dict[str, Any],
    skills_details: Dict[str, Any],
    details: Dict[str, Any],
    thresholds: XAIThresholds = DEFAULT_XAI_THRESHOLDS
) -> List[Dict[str, Any]]:
    """Genera i top motivi positivi per il match (max 5)."""
    reasons = []
    
    # 1. SEMANTIC SIMILARITY
    cosine_val = feature_values.get('cosine_similarity_normalized', 0)
    cosine_contrib = feature_contributions.get('cosine_similarity_normalized', 0)
    
    if cosine_val >= thresholds.COSINE_STRONG:
        reasons.append({
            "reason_id": "semantic_match_strong",
            "category": "profile_fit",
            "text": REASON_TEMPLATES["semantic_match_strong"],
            "contribution": round(cosine_contrib, 4),
            "evidence": "Competenze ed esperienze in linea con il ruolo"
        })
    elif cosine_val >= thresholds.COSINE_MODERATE:
        reasons.append({
            "reason_id": "semantic_match_moderate",
            "category": "profile_fit",
            "text": REASON_TEMPLATES["semantic_match_moderate"],
            "contribution": round(cosine_contrib, 4),
            "evidence": "Background professionale compatibile"
        })
    
    # 2. CORE SKILLS
    skill_core_val = feature_values.get('skill_overlap_core_norm', 0)
    skill_core_contrib = feature_contributions.get('skill_overlap_core_norm', 0)
    matched = skills_details.get('cv_skills_matched', 0)
    plural = "i" if matched != 1 else "e"
    skill_evidence = f"{matched} skill core present{plural}"
    
    if skill_core_val >= thresholds.SKILL_CORE_STRONG:
        reasons.append({
            "reason_id": "core_skills_strong",
            "category": "skills",
            "text": REASON_TEMPLATES["core_skills_strong"],
            "contribution": round(skill_core_contrib, 4),
            "evidence": skill_evidence
        })
    elif skill_core_val >= thresholds.SKILL_CORE_PARTIAL:
        reasons.append({
            "reason_id": "core_skills_partial",
            "category": "skills",
            "text": REASON_TEMPLATES["core_skills_partial"],
            "contribution": round(skill_core_contrib, 4),
            "evidence": skill_evidence
        })
    
    # 3. NICE-TO-HAVE SKILLS
    skill_nice_val = feature_values.get('skill_overlap_nice_norm', 0)
    skill_nice_contrib = feature_contributions.get('skill_overlap_nice_norm', 0)
    nice_matched = skills_details.get('nice_to_have_matched', 0)
    
    if skill_nice_val >= thresholds.SKILL_NICE_THRESHOLD and nice_matched > 0:
        reasons.append({
            "reason_id": "nice_skills_present",
            "category": "skills",
            "text": REASON_TEMPLATES["nice_skills_present"],
            "contribution": round(skill_nice_contrib, 4),
            "evidence": f"{nice_matched} skill nice-to-have presenti"
        })
    
    # 4. EXPERIENCE
    exp_meets = feature_values.get('experience_meets_requirement', 0)
    exp_contrib = feature_contributions.get('experience_meets_requirement', 0)
    years_cv = experience_details.get('cv_years', 0)
    years_jd = experience_details.get('required_years', 0)
    years_cv_int = int(round(years_cv))
    years_jd_int = int(round(years_jd))
    
    if exp_meets == 1.0:
        exp_evidence = f"{years_cv_int} anni (richiesti: {years_jd_int})"
        if years_jd > 0 and years_cv >= years_jd * 1.5:
            reasons.append({
                "reason_id": "experience_exceeds",
                "category": "experience",
                "text": REASON_TEMPLATES["experience_exceeds"],
                "contribution": round(exp_contrib, 4),
                "evidence": exp_evidence
            })
        else:
            reasons.append({
                "reason_id": "experience_sufficient",
                "category": "experience",
                "text": REASON_TEMPLATES["experience_sufficient"],
                "contribution": round(exp_contrib, 4),
                "evidence": exp_evidence
            })
    
    # 5. SENIORITY
    seniority_match = feature_values.get('seniority_match', 0)
    seniority_contrib = feature_contributions.get('seniority_match', 0)
    seniority_cv = seniority_details.get('cv_seniority', '')
    seniority_jd = seniority_details.get('required_seniority', '')
    seniority_gap = seniority_details.get('gap', 0)
    
    if seniority_match == 1.0 and seniority_cv and seniority_jd:
        reasons.append({
            "reason_id": "seniority_aligned",
            "category": "seniority",
            "text": REASON_TEMPLATES["seniority_aligned"],
            "contribution": round(seniority_contrib, 4),
            "evidence": f"Seniority: {seniority_cv} (richiesta: {seniority_jd})"
        })
    elif seniority_gap > 0 and seniority_cv and seniority_jd:
        reasons.append({
            "reason_id": "seniority_higher",
            "category": "seniority",
            "text": REASON_TEMPLATES["seniority_higher"],
            "contribution": round(seniority_contrib, 4),
            "evidence": f"Seniority: {seniority_cv} > {seniority_jd} richiesta"
        })
    
    # 6. ROLE COHERENT
    role_coherent = feature_values.get('role_coherent', 0)
    role_contrib = feature_contributions.get('role_coherent', 0)
    cv_role = details.get('cv_current_role', '')
    
    if role_coherent == 1.0 and cv_role:
        reasons.append({
            "reason_id": "role_aligned",
            "category": "role",
            "text": REASON_TEMPLATES["role_aligned"],
            "contribution": round(role_contrib, 4),
            "evidence": f"Ruolo attuale: {cv_role}"
        })
    
    # Ordina per contributo e ritorna top 5
    reasons.sort(key=lambda x: x['contribution'], reverse=True)
    return reasons[:5]


def build_main_risks(
    feature_values: Dict[str, float],
    feature_contributions: Dict[str, float],
    experience_details: Dict[str, Any],
    seniority_details: Dict[str, Any],
    skills_details: Dict[str, Any],
    thresholds: XAIThresholds = DEFAULT_XAI_THRESHOLDS
) -> List[Dict[str, Any]]:
    """Genera i principali rischi/gap del match (max 3)."""
    risks = []
    
    # 1. MUST-HAVE SKILLS MANCANTI
    must_have_missing = feature_values.get('must_have_missing', 0)
    must_have_contrib = feature_contributions.get('must_have_missing', 0)
    
    if must_have_missing > 0:
        missing_count = skills_details.get('must_have_missing', int(must_have_missing))
        skill_evidence = f"{missing_count} skill core non chiaramente esplicite nel CV"
        severity = "high" if missing_count >= thresholds.MISSING_SKILLS_HIGH else "medium"
        template_key = f"missing_core_skills_{severity}"
        
        risks.append({
            "risk_id": "missing_core_skills",
            "category": "skills",
            "severity": severity,
            "text": f"{RISK_TEMPLATES[template_key]} ({missing_count})",
            "contribution": round(must_have_contrib, 4),
            "evidence": skill_evidence,
            "missing_count": missing_count
        })
    
    # 2. SENIORITY MISMATCH STRONG
    seniority_mismatch = feature_values.get('seniority_mismatch_strong', 0)
    seniority_mismatch_contrib = feature_contributions.get('seniority_mismatch_strong', 0)
    seniority_cv = seniority_details.get('cv_seniority', '')
    seniority_jd = seniority_details.get('required_seniority', '')
    
    if seniority_mismatch == 1.0:
        seniority_evidence = f"Candidato: {seniority_cv}, richiesta: {seniority_jd}" if seniority_cv and seniority_jd else "Gap di 2+ livelli"
        risks.append({
            "risk_id": "seniority_gap_critical",
            "category": "seniority",
            "severity": "high",
            "text": RISK_TEMPLATES["seniority_gap_critical"],
            "contribution": round(seniority_mismatch_contrib, 4),
            "evidence": seniority_evidence
        })
    
    # 3. UNDERSKILLED
    underskilled = feature_values.get('seniority_underskilled', 0)
    underskilled_contrib = feature_contributions.get('seniority_underskilled', 0)
    has_seniority_critical = any(r['risk_id'] == 'seniority_gap_critical' for r in risks)
    
    if underskilled == 1.0 and not has_seniority_critical:
        underskilled_evidence = f"Candidato: {seniority_cv}, richiesta: {seniority_jd}" if seniority_cv and seniority_jd else "Seniority insufficiente"
        risks.append({
            "risk_id": "underskilled",
            "category": "seniority",
            "severity": "medium",
            "text": RISK_TEMPLATES["underskilled"],
            "contribution": round(underskilled_contrib, 4),
            "evidence": underskilled_evidence
        })
    
    # 4. ESPERIENZA INSUFFICIENTE
    exp_meets = feature_values.get('experience_meets_requirement', 1)
    exp_penalty_contrib = feature_contributions.get('experience_penalty_soft', 0)
    years_cv = experience_details.get('cv_years', 0)
    years_jd = experience_details.get('required_years', 0)
    
    if exp_meets == 0 and years_jd > 0:
        gap = years_jd - years_cv
        gap_int = int(round(gap))
        years_cv_int = int(round(years_cv))
        years_jd_int = int(round(years_jd))
        severity = "high" if gap >= thresholds.EXPERIENCE_GAP_HIGH else "medium"
        template_key = f"experience_below_{'critical' if severity == 'high' else 'minor'}"
        
        risks.append({
            "risk_id": "experience_below_requirement",
            "category": "experience",
            "severity": severity,
            "text": f"{RISK_TEMPLATES[template_key]} ({gap_int} anni di gap)",
            "contribution": round(exp_penalty_contrib, 4),
            "evidence": f"Candidato: {years_cv_int} anni, richiesti: {years_jd_int} anni"
        })
    
    # Ordina per severità e impatto
    severity_order = {"high": 0, "medium": 1, "low": 2}
    risks.sort(key=lambda x: (severity_order.get(x['severity'], 2), x['contribution']))
    return risks[:3]


def build_evidence_summary(
    experience_details: Dict[str, Any],
    seniority_details: Dict[str, Any],
    skills_details: Dict[str, Any],
    details: Dict[str, Any]
) -> Dict[str, Any]:
    """Costruisce un riepilogo delle evidenze concrete."""
    years_cv = experience_details.get('cv_years', 0)
    years_jd = experience_details.get('required_years', 0)
    experience_gap = experience_details.get('gap', years_cv - years_jd)
    
    return {
        "skills_core_matched": skills_details.get('cv_skills_matched', 0),
        "skills_core_required": skills_details.get('jd_skills_required', 0),
        "skills_core_missing": skills_details.get('must_have_missing', 0),
        "skills_nice_matched": skills_details.get('nice_to_have_matched', 0),
        "skills_nice_total": skills_details.get('nice_to_have_total', 0),
        "cv_current_role": details.get('cv_current_role', ''),
        "experience_cv_years": int(round(years_cv)),
        "experience_jd_required": int(round(years_jd)),
        "experience_gap": int(round(experience_gap)),
        "seniority_cv": seniority_details.get('cv_seniority', ''),
        "seniority_jd": seniority_details.get('required_seniority', ''),
        "seniority_gap": seniority_details.get('gap', 0),
        "cv_completeness": details.get('cv_completeness_score', 0)
    }


def build_xai(
    feature_values: Dict[str, float],
    feature_contributions: Dict[str, float],
    experience_details: Dict[str, Any],
    seniority_details: Dict[str, Any],
    skills_details: Dict[str, Any],
    details: Dict[str, Any],
    final_score: float
) -> Dict[str, Any]:
    """Costruisce l'output XAI completo per il candidato."""
    
    # Quality label
    if final_score >= 0.5:
        quality_label = "EXCELLENT"
    elif final_score >= 0.3:
        quality_label = "GOOD"
    else:
        quality_label = "WEAK"
    
    # Build components
    top_reasons = build_top_reasons(
        feature_values, feature_contributions,
        experience_details, seniority_details, skills_details, details
    )
    main_risks = build_main_risks(
        feature_values, feature_contributions,
        experience_details, seniority_details, skills_details
    )
    evidence = build_evidence_summary(
        experience_details, seniority_details, skills_details, details
    )
    
    return {
        "quality_label": quality_label,
        "top_reasons": top_reasons,
        "main_risks": main_risks,
        "evidence": evidence
    }


# ============================================================================
# OUTPUT BUILDING
# ============================================================================

def build_json(user_id: str, jd_id: str, features: Dict, score: Dict,
               jd_data: pd.DataFrame, config: Config) -> Dict:
    """Costruisce JSON output strutturato per il match con XAI."""
    jd_row = jd_data[jd_data['jd_id'] == jd_id].iloc[0]
    jd_title = jd_row.get('title', '')

    feature_values = {}
    for feat in config.WEIGHTS.keys():
        val = features.get(feat, 0)
        feature_values[feat] = round(float(val) if pd.notna(val) else 0, 4)

    # Build details structures
    experience_details = {
        'cv_years': round(float(features.get('years_experience_cv', 0)), 1),
        'required_years': round(float(features.get('years_required_jd', 0)), 1),
        'gap': round(float(features.get('experience_gap', 0)), 1),
        'meets_requirement': bool(features.get('experience_meets_requirement', 0))
    }
    
    seniority_details = {
        'cv_seniority': str(features.get('seniority_cv_str', 'unknown')),
        'required_seniority': str(features.get('seniority_jd_str', 'unknown')),
        'cv_level': int(features.get('seniority_cv_level', 0)),
        'required_level': int(features.get('seniority_jd_level', 0)),
        'gap': int(features.get('seniority_gap', 0)),
        'match': bool(features.get('seniority_match', 0))
    }
    
    skills_details = {
        'cv_skills_matched': int(features.get('skill_overlap_core_abs', 0)),
        'jd_skills_required': int(features.get('jd_requirements_count', 0)),
        'match_ratio': round(float(features.get('skill_overlap_core_norm', 0)), 4),
        'nice_to_have_matched': int(features.get('skill_overlap_nice_abs', 0)),
        'nice_to_have_total': int(features.get('jd_nice_to_have_count', 0)),
        'must_have_missing': int(features.get('must_have_missing', 0))
    }
    
    details = {
        'skills_matched': features.get('_skills_matched', []),
        'skills_nice_matched': features.get('_skills_nice_matched', []),
        'cv_skills': features.get('_cv_skills', []),
        'jd_requirements': features.get('_jd_requirements', []),
        'jd_nice_to_have': features.get('_jd_nice_to_have', []),
        'cv_current_role': features.get('cv_current_role', ''),
        'cv_completeness_score': features.get('cv_completeness_score', 0)
    }

    # Build XAI
    xai = build_xai(
        feature_values, score['contributions'],
        experience_details, seniority_details, skills_details, details,
        score['final_score']
    )

    candidate = {
        'user_id': user_id,
        'rank': 1,
        'score': score['final_score'],
        'score_breakdown': {
            'linear_score_raw': score['linear_score_raw'],
            'linear_score_normalized': score['linear_score_normalized'],
            'dei_boost': score['dei_boost'],
            'final_score': score['final_score']
        },
        'experience_details': experience_details,
        'seniority_details': seniority_details,
        'skills_details': skills_details,
        'feature_values': feature_values,
        'feature_contributions': score['contributions'],
        'flags': {
            'seniority_mismatch_strong': bool(features.get('seniority_mismatch_strong', 0)),
            'underskilled': bool(features.get('seniority_underskilled', 0)),
            'experience_below_requirement': features.get('experience_meets_requirement', 1) == 0,
            'has_dei_tag': features.get('dei_tag_count', 0) > 0
        },
        'dei_tags': {
            'women': bool(features.get('tag_women', 0)),
            'protected_category': bool(features.get('tag_protected_category', 0))
        },
        'details': details,
        'xai': xai  # <-- XAI INTEGRATO
    }

    return {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'comparison_type': 'user_single_jd',
            'scoring_method': 'linear_weighted_model',
            'version': '1.3.0',
            'weights': config.WEIGHTS,
            'notes': 'v1.3.0: Integrated XAI explanations'
        },
        'job_description': {'jd_id': jd_id, 'title': jd_title},
        'candidate': candidate,
        'quality_assessment': {
            'cosine_similarity': features.get('cosine_similarity_raw', 0),
            'quality_label': get_quality_label(features.get('cosine_similarity_raw', 0), config),
            'final_score': score['final_score']
        }
    }


# ============================================================================
# VALIDATION
# ============================================================================

def validate_inputs(user_id: str, jd_id: str, data: dict) -> Tuple[bool, Optional[str]]:
    """Valida che user_id e jd_id esistano nei dataset."""
    # Collect available ids from embeddings and datasets (as strings)
    try:
        cv_ids = set(map(str, data['cv_emb_df']['user_id'].values))
    except Exception:
        cv_ids = set()

    try:
        cv_dataset_ids = set(map(str, data['cv_data']['user_id'].values))
    except Exception:
        cv_dataset_ids = set()

    try:
        jd_ids = set(map(str, data['jd_emb_df']['jd_id'].values))
    except Exception:
        jd_ids = set()

    try:
        jd_dataset_ids = set(map(str, data['jd_data']['jd_id'].values))
    except Exception:
        jd_dataset_ids = set()

    # Check user_id presence (prefer embeddings first)
    if user_id not in cv_ids and user_id not in cv_dataset_ids:
        sample = list(cv_dataset_ids or cv_ids)[:5]
        suggestions = difflib.get_close_matches(user_id, list(cv_dataset_ids or cv_ids), n=5, cutoff=0.4)
        hint = ''
        if sample:
            hint = f"Esempi presenti: {sample}."
        if suggestions:
            hint = (hint + ' Suggerimenti simili: ' + str(suggestions)) if hint else ('Suggerimenti simili: ' + str(suggestions))
        return False, f"USER_ID '{user_id}' non trovato nel dataset CV. {hint}"

    # Check jd_id presence
    if jd_id not in jd_ids and jd_id not in jd_dataset_ids:
        sample = list(jd_dataset_ids or jd_ids)[:5]
        suggestions = difflib.get_close_matches(jd_id, list(jd_dataset_ids or jd_ids), n=5, cutoff=0.4)
        hint = ''
        if sample:
            hint = f"Esempi presenti: {sample}."
        if suggestions:
            hint = (hint + ' Suggerimenti simili: ' + str(suggestions)) if hint else ('Suggerimenti simili: ' + str(suggestions))
        return False, f"JD_ID '{jd_id}' non trovato nel dataset JD. {hint}"

    return True, None


# ============================================================================
# MAIN BACKEND FUNCTION
# ============================================================================

def compare_cv_with_jd(user_id: str, jd_id: str, 
                       config: Optional[Config] = None,
                       data: Optional[dict] = None) -> Dict:
    """
    Funzione principale per il backend: confronta un CV con una JD.
    
    Args:
        user_id (str): ID dell'utente/CV da confrontare
        jd_id (str): ID della job description
        config (Config, optional): Configurazione custom
        data (dict, optional): Dati precaricati
    
    Returns:
        dict: JSON strutturato con risultati match, score, feature, flags, XAI
    """
    if config is None:
        config = Config()
    
    if data is None:
        data = load_all_data(config)
    
    is_valid, error_msg = validate_inputs(user_id, jd_id, data)
    if not is_valid:
        raise ValueError(error_msg)
    
    cv_emb = data['cv_embeddings'][user_id]
    jd_emb = data['jd_embeddings'][jd_id]
    cosine = cosine_similarity(cv_emb, jd_emb)
    
    features = compute_features(user_id, jd_id, cosine, 
                               data['cv_data'], data['jd_data'], config)
    
    score = compute_score(features, config)
    
    output = build_json(user_id, jd_id, features, score, data['jd_data'], config)
    
    return output

app = FastAPI()

# Abilita CORS per sviluppo frontend locale
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

class MatchRequest(BaseModel):
    user_id: str
    jd_id: str

@app.get("/api/match_cv_jd")
def match_cv_jd(user_id: str = Query(...), jd_id: str = Query(...)):
    try:
        result = compare_cv_with_jd(user_id, jd_id)
        return result
    except ValueError as e:
        # Known validation error (missing ids etc.) -> return 404 with message
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        # Unexpected errors -> internal server error with clear prefix
        raise HTTPException(status_code=500, detail=f"Matcher internal error: {str(e)}")


@app.post("/api/match_cv_jd")
async def match_cv_jd_post(request: MatchRequest):
    """POST compatibile: accetta JSON con `user_id` e `jd_id` e richiama lo stesso matcher.

    Permette al frontend e a tool come `curl -X POST -d '{"user_id":"...","jd_id":"..."}'`
    di usare l'API in modo sicuro.
    """
    try:
        result = compare_cv_with_jd(request.user_id, request.jd_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Matcher internal error: {str(e)}")

# Per test locale: uvicorn single_match:app --reload
if __name__ == "__main__":
    uvicorn.run("single_match:app", host="0.0.0.0", port=8000, reload=True)
