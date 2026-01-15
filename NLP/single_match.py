"""
User CV Matcher - Confronto singolo CV con JD
Usa la stessa pipeline del reranker aziendale.
"""

import json
import re
import warnings
from pathlib import Path
from typing import Dict, Set, Tuple, Optional
from datetime import datetime
from dataclasses import dataclass, field

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')


@dataclass
class Config:
    """Configurazione per il matcher"""
    EMBEDDINGS_DIR: Path = Path("embeddings")
    CV_EMBEDDINGS_FILE: str = "cv_embeddings.csv"
    JD_EMBEDDINGS_FILE: str = "jd_embeddings.csv"
    CV_DATASET_PATH: Path = Path("Dataset/normalized/cv_dataset_normalized.csv")
    JD_DATASET_PATH: Path = Path("Dataset/normalized/jd_dataset_normalized.csv")

    QUALITY_THRESHOLDS: Dict[str, float] = field(default_factory=lambda: {
        'excellent': 0.5, 'good': 0.3, 'weak': 0.0
    })
    
    SENIORITY_LEVELS: Dict[str, int] = field(default_factory=lambda: {
        'junior': 1, 'mid': 2, 'senior': 3
    })
    
    WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        'cosine_similarity_normalized': 0.30,
        'skill_overlap_core_norm': 0.15,
        'skill_coverage_total': 0.05,
        'skill_overlap_nice_norm': 0.05,
        'experience_meets_requirement': 0.20,
        'seniority_match': 0.15,
        'role_similarity_jaccard': 0.05,
        'role_coherent': 0.05,
        'must_have_missing': -0.05,
        'experience_penalty_soft': -0.10,
        'seniority_mismatch_strong': -0.15,
        'seniority_underskilled': -0.05,
    })
    
    EXPERIENCE_GAP_PENALTY_FACTOR: float = 0.1
    DEI_TAG_BOOST: float = 0.05


# ============================================================================
# UTILITY FUNCTIONS
# ============================================================================

def load_embeddings(csv_path: Path) -> Tuple[pd.DataFrame, Dict[str, np.ndarray]]:
    """Carica embeddings da CSV"""
    df = pd.read_csv(csv_path)
    id_col = 'user_id' if 'user_id' in df.columns else 'jd_id'
    embeddings_dict = {}
    for _, row in df.iterrows():
        entity_id = row[id_col]
        embedding = np.array(json.loads(row['embedding_vector']))
        embeddings_dict[entity_id] = embedding
    return df, embeddings_dict


def load_normalized_datasets(config: Config) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Carica dataset normalizzati CV e JD"""
    cv_data = pd.read_csv(config.CV_DATASET_PATH)
    jd_data = pd.read_csv(config.JD_DATASET_PATH)
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


def extract_years_from_requirements(req_str: str) -> Optional[int]:
    """Estrae anni di esperienza richiesti dalla stringa requirements"""
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
    """
    Calcola tutte le feature per una coppia (CV, JD).
    
    Args:
        user_id: ID dell'utente/CV
        jd_id: ID della job description
        cosine_sim: Similarità coseno tra embeddings
        cv_data: DataFrame con CV normalizzati
        jd_data: DataFrame con JD normalizzati
        config: Configurazione
    
    Returns:
        Dict con tutte le feature calcolate
    """
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

    features['skill_overlap_core_abs'] = len(core_overlap)
    features['skill_overlap_core_norm'] = len(core_overlap) / len(jd_req) if jd_req else 0.0
    features['skill_overlap_nice_abs'] = len(nice_overlap)
    features['skill_overlap_nice_norm'] = len(nice_overlap) / len(jd_nice) if jd_nice else 0.0
    features['skill_coverage_total'] = len(all_overlap) / len(all_jd) if all_jd else 0.0
    features['must_have_missing'] = len(jd_req) - len(core_overlap)
    features['_cv_skills'] = list(cv_skills)
    features['_jd_requirements'] = list(jd_req)
    features['_jd_nice_to_have'] = list(jd_nice)
    features['_skills_matched'] = list(core_overlap)
    features['_skills_nice_matched'] = list(nice_overlap)

    # ---- EXPERIENCE ANALYSIS ----
    cv_years = cv_row.get('years_of_experience', 0)
    cv_years = 0 if pd.isna(cv_years) else float(cv_years)
    jd_years = extract_years_from_requirements(jd_row.get('requirements', ''))
    jd_years = 0 if jd_years is None else jd_years
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
    """
    Calcola score finale usando weighted linear combination.
    
    Args:
        features: Dict con feature calcolate
        config: Configurazione con pesi
    
    Returns:
        Dict con score breakdown e contributi per feature
    """
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
# OUTPUT BUILDING
# ============================================================================

def build_json(user_id: str, jd_id: str, features: Dict, score: Dict,
               jd_data: pd.DataFrame, config: Config) -> Dict:
    """
    Costruisce JSON output strutturato per il match.
    
    Args:
        user_id: ID utente
        jd_id: ID job description
        features: Dict con feature
        score: Dict con score
        jd_data: DataFrame JD
        config: Configurazione
    
    Returns:
        Dict strutturato con metadata, candidate, quality assessment
    """
    jd_row = jd_data[jd_data['jd_id'] == jd_id].iloc[0]
    jd_title = jd_row.get('title', '')

    feature_values = {}
    for feat in config.WEIGHTS.keys():
        val = features.get(feat, 0)
        feature_values[feat] = round(float(val) if pd.notna(val) else 0, 4)

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
        'details': {
            'skills_matched': features.get('_skills_matched', []),
            'skills_nice_matched': features.get('_skills_nice_matched', []),
            'cv_skills': features.get('_cv_skills', []),
            'jd_requirements': features.get('_jd_requirements', []),
            'jd_nice_to_have': features.get('_jd_nice_to_have', []),
            'cv_current_role': features.get('cv_current_role', ''),
            'years_experience_cv': features.get('years_experience_cv', 0),
            'years_required_jd': features.get('years_required_jd', 0),
            'seniority_cv': features.get('seniority_cv', ''),
            'seniority_jd': features.get('seniority_jd', ''),
            'cv_completeness_score': features.get('cv_completeness_score', 0)
        }
    }

    return {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'comparison_type': 'user_single_jd',
            'scoring_method': 'linear_weighted_model',
            'version': '1.0',
            'weights': config.WEIGHTS
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
    """
    Valida che user_id e jd_id esistano nei dataset.
    
    Args:
        user_id: ID utente da validare
        jd_id: ID JD da validare
        data: Dict con tutti i dati caricati
    
    Returns:
        Tuple (is_valid, error_message)
    """
    if user_id not in data['cv_emb_df']['user_id'].values:
        return False, f"USER_ID '{user_id}' non trovato nel dataset CV"
    
    if jd_id not in data['jd_emb_df']['jd_id'].values:
        return False, f"JD_ID '{jd_id}' non trovato nel dataset JD"
    
    return True, None


# ============================================================================
# MAIN BACKEND FUNCTION
# ============================================================================

def compare_cv_with_jd(user_id: str, jd_id: str, 
                       config: Optional[Config] = None,
                       data: Optional[dict] = None) -> Dict:
    """
    Funzione principale per il backend: confronta un CV con una JD.
    
    Richiamata dal backend quando l'utente clicca il bottone nel frontend.
    
    Args:
        user_id (str): ID dell'utente/CV da confrontare
        jd_id (str): ID della job description
        config (Config, optional): Configurazione custom. Se None, usa default.
        data (dict, optional): Dati precaricati (embeddings + dataset).
                               Se None, li carica automaticamente.
    
    Returns:
        dict: JSON strutturato con risultati match, score, feature, flags, etc.
        
    Raises:
        ValueError: Se user_id o jd_id non sono trovati nei dataset
        FileNotFoundError: Se i file di embedding/dataset non esistono
    """
    # Setup config
    if config is None:
        config = Config()
    
    # Caricamento dati (una volta sola se passati)
    if data is None:
        data = load_all_data(config)
    
    # Validazione input
    is_valid, error_msg = validate_inputs(user_id, jd_id, data)
    if not is_valid:
        raise ValueError(error_msg)
    
    # Calcolo similarità coseno
    cv_emb = data['cv_embeddings'][user_id]
    jd_emb = data['jd_embeddings'][jd_id]
    cosine = cosine_similarity(cv_emb, jd_emb)
    
    # Feature engineering
    features = compute_features(user_id, jd_id, cosine, 
                               data['cv_data'], data['jd_data'], config)
    
    # Scoring
    score = compute_score(features, config)
    
    # Build output JSON
    output = build_json(user_id, jd_id, features, score, data['jd_data'], config)
    
    return output
