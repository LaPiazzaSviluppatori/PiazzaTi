"""
RERANKER - FEATURE ENGINEERING MODULE
Calcola feature esplicite e interpretabili per il reranking delle coppie CV-JD.

AGGIORNAMENTO: usa min_experience_years_normalized invece di estrarre anni da requirements
"""

import pandas as pd
import numpy as np
import re
from typing import Dict, List, Set, Tuple, Optional
from dataclasses import dataclass
from pathlib import Path
import warnings
warnings.filterwarnings('ignore')


@dataclass
class Config:
    RERANKER_INPUT_PATH: str = "match_results/reranker_input.csv"
    CV_DATASET_PATH: str = "Dataset/normalized/cv_dataset_normalized.csv"
    JD_DATASET_PATH: str = "Dataset/normalized/jd_dataset_normalized.csv"
    OUTPUT_PATH: str = "rerank_results/reranker_features.csv"
    
    # Fattore di penalità per gap esperienza negativo
    # Es: se mancano 2 anni, penalty = 2 * 0.1 = 0.2
    EXPERIENCE_GAP_PENALTY_FACTOR: float = 0.1
    
    # Fattore di bonus per esperienza extra (più basso della penalità)
    # Es: se hai 2 anni in più, bonus = 2 * 0.02 = 0.04
    EXPERIENCE_EXTRA_BONUS_FACTOR: float = 0.02
    
    # Soglia oltre la quale l'esperienza extra non dà più bonus
    EXPERIENCE_EXTRA_CAP: float = 5.0
    
    SENIORITY_LEVELS: Dict[str, int] = None
    LANGUAGE_LEVELS: Dict[str, int] = None

    def __post_init__(self):
        self.SENIORITY_LEVELS = {'junior': 1, 'mid': 2, 'senior': 3}
        self.LANGUAGE_LEVELS = {
            'a1': 1, 'a2': 2, 'b1': 3, 'b2': 4, 'c1': 5, 'c2': 6,
            'native': 6, 'madrelingua': 6
        }

config = Config()


def load_data(config: Config) -> Tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    reranker_input = pd.read_csv(config.RERANKER_INPUT_PATH)
    cv_data = pd.read_csv(config.CV_DATASET_PATH)
    jd_data = pd.read_csv(config.JD_DATASET_PATH)

    print(f"Loaded: {len(reranker_input)} pairs, {len(cv_data)} CVs, {len(jd_data)} JDs")
    return reranker_input, cv_data, jd_data


def parse_skills_string(skills_str: str) -> Set[str]:
    if pd.isna(skills_str) or skills_str == '':
        return set()
    skills = set()
    for skill in str(skills_str).split(','):
        clean_skill = skill.strip().lower()
        clean_skill = re.sub(r'^[\*e\s]+', '', clean_skill)
        if clean_skill:
            skills.add(clean_skill)
    return skills


def parse_languages_string(lang_str: str) -> Dict[str, str]:
    if pd.isna(lang_str) or lang_str == '':
        return {}
    languages = {}
    pattern = r'([A-Za-z]+)\s*\(([A-Za-z0-9]+)\)'
    matches = re.findall(pattern, str(lang_str))
    for lang, level in matches:
        languages[lang.lower()] = level.lower()
    return languages


def get_seniority_numeric(seniority: str, config: Config) -> int:
    if pd.isna(seniority):
        return 0
    return config.SENIORITY_LEVELS.get(str(seniority).lower(), 0)


def get_language_level_numeric(level: str, config: Config) -> int:
    if pd.isna(level):
        return 0
    return config.LANGUAGE_LEVELS.get(str(level).lower(), 0)


def extract_current_role_from_experience(experience_str: str) -> str:
    """Estrae il titolo del ruolo attuale (primo nella lista) dal campo experience."""
    if pd.isna(experience_str) or experience_str == '':
        return ''
    # Formato: "Titolo @ Company (Location) [dates] | ..."
    # Prende tutto prima di " @ "
    match = re.match(r'^([^@]+)\s*@', str(experience_str))
    if match:
        return match.group(1).strip().lower()
    return ''


def compute_role_similarity(cv_role: str, jd_title: str) -> Tuple[float, int]:
    """
    Calcola similarita tra titolo ruolo CV e titolo JD.
    Returns: (jaccard_similarity, exact_match_flag)
    """
    if not cv_role or not jd_title:
        return 0.0, 0

    cv_role = cv_role.lower()
    jd_title = jd_title.lower()

    # Tokenizza
    cv_tokens = set(re.findall(r'\w+', cv_role))
    jd_tokens = set(re.findall(r'\w+', jd_title))

    # Rimuovi stopwords comuni
    stopwords = {'a', 'an', 'the', 'of', 'in', 'at', 'for', 'and', 'or', 'di', 'e', 'il', 'la'}
    cv_tokens = cv_tokens - stopwords
    jd_tokens = jd_tokens - stopwords

    if not cv_tokens or not jd_tokens:
        return 0.0, 0

    # Jaccard
    intersection = len(cv_tokens & jd_tokens)
    union = len(cv_tokens | jd_tokens)
    jaccard = intersection / union if union > 0 else 0.0

    # Match esatto (almeno una parola chiave in comune)
    exact_match = 1 if intersection > 0 else 0

    return jaccard, exact_match


def compute_semantic_features(reranker_input: pd.DataFrame) -> pd.DataFrame:
    features = pd.DataFrame()
    features['jd_id'] = reranker_input['jd_id']
    features['user_id'] = reranker_input['user_id']
    features['cosine_similarity_raw'] = reranker_input['cosine_similarity']

    def normalize_within_group(group):
        min_val, max_val = group.min(), group.max()
        if max_val == min_val:
            return pd.Series([0.5] * len(group), index=group.index)
        return (group - min_val) / (max_val - min_val)

    features['cosine_similarity_normalized'] = (
        reranker_input.groupby('jd_id')['cosine_similarity']
        .transform(normalize_within_group)
    )
    return features


def compute_skills_features(
    reranker_input: pd.DataFrame,
    cv_data: pd.DataFrame,
    jd_data: pd.DataFrame
) -> pd.DataFrame:
    cv_skills_dict = dict(zip(cv_data['user_id'], cv_data['skills_normalized']))
    jd_req_dict = dict(zip(jd_data['jd_id'], jd_data['requirements_normalized']))
    jd_nice_dict = dict(zip(jd_data['jd_id'], jd_data['nice_to_have_normalized']))

    features = []
    for _, row in reranker_input.iterrows():
        jd_id, user_id = row['jd_id'], row['user_id']

        cv_skills = parse_skills_string(cv_skills_dict.get(user_id, ''))
        jd_requirements = parse_skills_string(jd_req_dict.get(jd_id, ''))
        jd_nice_to_have = parse_skills_string(jd_nice_dict.get(jd_id, ''))

        # NOTA: non serve più filtrare "X+ years" dai requirements
        # perché ora gli anni sono in una colonna separata (min_experience_years_normalized)

        core_overlap = cv_skills.intersection(jd_requirements)
        nice_overlap = cv_skills.intersection(jd_nice_to_have)

        skill_overlap_core_abs = len(core_overlap)
        skill_overlap_core_norm = len(core_overlap) / len(jd_requirements) if jd_requirements else 0.0
        skill_overlap_nice_abs = len(nice_overlap)
        skill_overlap_nice_norm = len(nice_overlap) / len(jd_nice_to_have) if jd_nice_to_have else 0.0

        all_jd_skills = jd_requirements.union(jd_nice_to_have)
        all_overlap = cv_skills.intersection(all_jd_skills)
        skill_coverage_total = len(all_overlap) / len(all_jd_skills) if all_jd_skills else 0.0

        must_have_missing = len(jd_requirements) - len(core_overlap)

        features.append({
            'jd_id': jd_id, 'user_id': user_id,
            'skill_overlap_core_abs': skill_overlap_core_abs,
            'skill_overlap_core_norm': skill_overlap_core_norm,
            'skill_overlap_nice_abs': skill_overlap_nice_abs,
            'skill_overlap_nice_norm': skill_overlap_nice_norm,
            'skill_coverage_total': skill_coverage_total,
            'must_have_missing': must_have_missing
        })

    return pd.DataFrame(features)


def compute_experience_features(
    reranker_input: pd.DataFrame,
    cv_data: pd.DataFrame,
    jd_data: pd.DataFrame,
    config: Config
) -> pd.DataFrame:
    """
    Calcola feature relative all'esperienza lavorativa.
    
    AGGIORNAMENTO: ora usa min_experience_years_normalized dalla JD
    invece di estrarre gli anni dal testo dei requirements.
    
    Questo garantisce:
    - Maggiore affidabilità (niente regex)
    - Coerenza con il resto della pipeline
    - Valori già validati e normalizzati
    """
    # Dizionari per lookup veloce
    cv_years_dict = dict(zip(cv_data['user_id'], cv_data['years_of_experience']))
    
    # AGGIORNAMENTO: usa min_experience_years_normalized invece di requirements
    # Fallback a min_experience_years se la colonna normalizzata non esiste
    if 'min_experience_years_normalized' in jd_data.columns:
        jd_years_dict = dict(zip(jd_data['jd_id'], jd_data['min_experience_years_normalized']))
        print("  [experience] Usando min_experience_years_normalized")
    elif 'min_experience_years' in jd_data.columns:
        jd_years_dict = dict(zip(jd_data['jd_id'], jd_data['min_experience_years']))
        print("  [experience] Usando min_experience_years (non normalizzato)")
    else:
        # Fallback legacy: estrai da requirements (per retrocompatibilità)
        print("  [experience] ⚠ Colonna min_experience_years non trovata, usando fallback regex")
        jd_years_dict = {}
        for _, row in jd_data.iterrows():
            jd_id = row['jd_id']
            req = row.get('requirements', '')
            years = _extract_years_from_requirements_legacy(req)
            jd_years_dict[jd_id] = years if years else 0

    features = []
    for _, row in reranker_input.iterrows():
        jd_id, user_id = row['jd_id'], row['user_id']

        # Anni di esperienza del candidato (dal CV normalizzato)
        cv_years = cv_years_dict.get(user_id, 0)
        cv_years = float(cv_years) if pd.notna(cv_years) else 0.0

        # Anni minimi richiesti dalla JD
        jd_years = jd_years_dict.get(jd_id, 0)
        jd_years = float(jd_years) if pd.notna(jd_years) else 0.0

        # Gap = CV - JD (positivo se il candidato ha più esperienza)
        experience_gap = cv_years - jd_years
        
        # Penalità se sotto-qualificato (gap negativo)
        # Più anni mancano, più alta è la penalità
        if experience_gap < 0:
            experience_penalty_soft = abs(experience_gap) * config.EXPERIENCE_GAP_PENALTY_FACTOR
        else:
            experience_penalty_soft = 0.0
        
        # Bonus se sovra-qualificato (gap positivo), con cap
        # Un po' di esperienza extra è positivo, troppa potrebbe indicare overqualification
        if experience_gap > 0:
            capped_extra = min(experience_gap, config.EXPERIENCE_EXTRA_CAP)
            experience_bonus = capped_extra * config.EXPERIENCE_EXTRA_BONUS_FACTOR
        else:
            experience_bonus = 0.0
        
        # Flag: soddisfa il requisito minimo?
        experience_meets_requirement = 1 if cv_years >= jd_years else 0
        
        # Flag: significativamente sotto-qualificato (mancano 2+ anni)?
        experience_significantly_under = 1 if experience_gap <= -2 else 0
        
        # Flag: potenzialmente sovra-qualificato (5+ anni in più)?
        experience_overqualified = 1 if experience_gap >= 5 else 0

        features.append({
            'jd_id': jd_id, 
            'user_id': user_id,
            'years_experience_cv': round(cv_years, 1),
            'years_required_jd': round(jd_years, 1),
            'experience_gap': round(experience_gap, 1),
            'experience_gap_abs': round(abs(experience_gap), 1),
            'experience_meets_requirement': experience_meets_requirement,
            'experience_penalty_soft': round(experience_penalty_soft, 4),
            'experience_bonus': round(experience_bonus, 4),
            'experience_significantly_under': experience_significantly_under,
            'experience_overqualified': experience_overqualified
        })

    return pd.DataFrame(features)


def _extract_years_from_requirements_legacy(req_str: str) -> Optional[int]:
    """
    LEGACY: Estrae anni di esperienza dal testo dei requirements.
    Usato solo come fallback se min_experience_years non è disponibile.
    
    DEPRECATO: preferire l'uso di min_experience_years_normalized.
    """
    if pd.isna(req_str):
        return None
    patterns = [r'(\d+)\+?\s*years?', r'(\d+)\+?\s*anni']
    for pattern in patterns:
        match = re.search(pattern, str(req_str).lower())
        if match:
            return int(match.group(1))
    return None


def compute_seniority_features(
    reranker_input: pd.DataFrame,
    cv_data: pd.DataFrame,
    jd_data: pd.DataFrame,
    config: Config
) -> pd.DataFrame:
    cv_seniority_dict = dict(zip(cv_data['user_id'], cv_data['inferred_seniority']))
    jd_seniority_dict = dict(zip(jd_data['jd_id'], jd_data['constraints_seniority_normalized']))

    features = []
    for _, row in reranker_input.iterrows():
        jd_id, user_id = row['jd_id'], row['user_id']

        cv_level = get_seniority_numeric(cv_seniority_dict.get(user_id, ''), config)
        jd_level = get_seniority_numeric(jd_seniority_dict.get(jd_id, ''), config)
        seniority_gap = cv_level - jd_level

        features.append({
            'jd_id': jd_id, 'user_id': user_id,
            'seniority_cv_level': cv_level,
            'seniority_jd_level': jd_level,
            'seniority_gap': seniority_gap,
            'seniority_match': 1 if cv_level == jd_level else 0,
            'seniority_mismatch_strong': 1 if abs(seniority_gap) >= 2 else 0,
            'seniority_underskilled': 1 if cv_level < jd_level else 0
        })

    return pd.DataFrame(features)


def compute_role_features(
    reranker_input: pd.DataFrame,
    cv_data: pd.DataFrame,
    jd_data: pd.DataFrame
) -> pd.DataFrame:
    """Calcola feature di coerenza e similarita tra ruolo CV e titolo JD."""
    cv_exp_dict = dict(zip(cv_data['user_id'], cv_data['experience']))
    jd_title_dict = dict(zip(jd_data['jd_id'], jd_data['title']))

    features = []
    for _, row in reranker_input.iterrows():
        jd_id, user_id = row['jd_id'], row['user_id']

        cv_role = extract_current_role_from_experience(cv_exp_dict.get(user_id, ''))
        jd_title = jd_title_dict.get(jd_id, '')
        jd_title_lower = jd_title.lower() if jd_title else ''

        role_similarity, role_token_match = compute_role_similarity(cv_role, jd_title_lower)

        # Coerenza: il ruolo CV contiene parole del titolo JD o viceversa
        role_coherent = 1 if role_similarity > 0.2 else 0

        features.append({
            'jd_id': jd_id, 'user_id': user_id,
            'role_similarity_jaccard': role_similarity,
            'role_token_match': role_token_match,
            'role_coherent': role_coherent
        })

    return pd.DataFrame(features)


def compute_parsing_quality_features(
    reranker_input: pd.DataFrame,
    cv_data: pd.DataFrame
) -> pd.DataFrame:
    cv_dict = cv_data.set_index('user_id').to_dict('index')

    features = []
    for _, row in reranker_input.iterrows():
        jd_id, user_id = row['jd_id'], row['user_id']
        cv_row = cv_dict.get(user_id, {})

        has_summary = 1 if pd.notna(cv_row.get('summary', '')) and cv_row.get('summary', '') != '' else 0
        has_experience = 1 if pd.notna(cv_row.get('experience', '')) and cv_row.get('experience', '') != '' else 0
        has_education = 1 if pd.notna(cv_row.get('education', '')) and cv_row.get('education', '') != '' else 0
        has_skills = 1 if pd.notna(cv_row.get('skills_normalized', '')) and cv_row.get('skills_normalized', '') != '' else 0
        has_languages = 1 if pd.notna(cv_row.get('languages_normalized', '')) and cv_row.get('languages_normalized', '') != '' else 0

        sections = [has_summary, has_experience, has_education, has_skills, has_languages]
        completeness_score = sum(sections) / len(sections)

        skills_str = cv_row.get('skills_normalized', '')
        skills_count = len(str(skills_str).split(',')) if pd.notna(skills_str) and skills_str != '' else 0

        features.append({
            'jd_id': jd_id, 'user_id': user_id,
            'cv_has_summary': has_summary,
            'cv_has_experience': has_experience,
            'cv_has_education': has_education,
            'cv_has_skills': has_skills,
            'cv_has_languages': has_languages,
            'cv_completeness_score': completeness_score,
            'cv_skills_count': skills_count
        })

    return pd.DataFrame(features)


def build_all_features(config: Config) -> pd.DataFrame:
    reranker_input, cv_data, jd_data = load_data(config)

    print("\nComputing features...")
    
    semantic_features = compute_semantic_features(reranker_input)
    print("  ✓ Semantic features")
    
    skills_features = compute_skills_features(reranker_input, cv_data, jd_data)
    print("  ✓ Skills features")
    
    experience_features = compute_experience_features(reranker_input, cv_data, jd_data, config)
    print("  ✓ Experience features")
    
    seniority_features = compute_seniority_features(reranker_input, cv_data, jd_data, config)
    print("  ✓ Seniority features")
    
    role_features = compute_role_features(reranker_input, cv_data, jd_data)
    print("  ✓ Role features")
    
    parsing_features = compute_parsing_quality_features(reranker_input, cv_data)
    print("  ✓ Parsing quality features")

    all_features = semantic_features.copy()
    all_features['retrieval_rank'] = reranker_input['rank'].values

    for feat_df in [skills_features, experience_features, seniority_features, role_features, parsing_features]:
        feat_df = feat_df.drop(columns=['jd_id', 'user_id'], errors='ignore')
        all_features = pd.concat([all_features, feat_df.reset_index(drop=True)], axis=1)

    id_cols = ['jd_id', 'user_id', 'retrieval_rank']
    other_cols = [c for c in all_features.columns if c not in id_cols]
    all_features = all_features[id_cols + sorted(other_cols)]

    Path(config.OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    all_features.to_csv(config.OUTPUT_PATH, index=False)
    
    print(f"\nOutput: {config.OUTPUT_PATH}")
    print(f"  Rows: {len(all_features)}")
    print(f"  Features: {len(all_features.columns) - 3}")
    
    # Statistiche esperienza
    print(f"\nExperience statistics:")
    print(f"  Candidates meeting requirements: {all_features['experience_meets_requirement'].sum()}/{len(all_features)} ({all_features['experience_meets_requirement'].mean()*100:.1f}%)")
    print(f"  Significantly under-qualified: {all_features['experience_significantly_under'].sum()}")
    print(f"  Potentially over-qualified: {all_features['experience_overqualified'].sum()}")
    print(f"  Avg experience gap: {all_features['experience_gap'].mean():.1f} years")

    return all_features


if __name__ == "__main__":
    features_df = build_all_features(config)


# =============================================================================
# RERANKER - DEI TAG ADJUSTMENT MODULE
# Aggiunge i tag DEI dai CV e applica adjustment alla classifica.
# =============================================================================

@dataclass
class DEIConfig:
    FEATURES_INPUT_PATH: str = "rerank_results/reranker_features.csv"
    CV_DATASET_PATH: str = "Dataset/normalized/cv_dataset_normalized.csv"
    JD_DATASET_PATH: str = "Dataset/normalized/jd_dataset_normalized.csv"
    OUTPUT_PATH: str = "rerank_results/reranker_features.csv"

    # Boost per ogni tag (aggiunto allo score normalizzato)
    TAG_BOOST: float = 0.05


dei_config = DEIConfig()


def load_dei_data(config: DEIConfig):
    features = pd.read_csv(config.FEATURES_INPUT_PATH)
    cv_data = pd.read_csv(config.CV_DATASET_PATH)
    jd_data = pd.read_csv(config.JD_DATASET_PATH)

    print(f"Loaded: {len(features)} pairs, {len(cv_data)} CVs, {len(jd_data)} JDs")
    return features, cv_data, jd_data


def add_dei_tags(features: pd.DataFrame, cv_data: pd.DataFrame) -> pd.DataFrame:
    """Aggiunge le colonne tag dal CV dataset."""
    tag_cols = ['tag_women', 'tag_protected_category']
    
    # Verifica quali colonne esistono effettivamente
    existing_tag_cols = [col for col in tag_cols if col in cv_data.columns]
    
    if not existing_tag_cols:
        print("  ⚠ Nessuna colonna tag trovata nel CV dataset")
        features['dei_tag_count'] = 0
        return features

    cv_tags = cv_data[['user_id'] + existing_tag_cols].copy()

    # Converti True/NaN in 1/0
    for col in existing_tag_cols:
        cv_tags[col] = cv_tags[col].notna().astype(int)

    # Merge con features
    result = features.merge(cv_tags, on='user_id', how='left')

    # Fill eventuali NaN rimasti
    for col in existing_tag_cols:
        result[col] = result[col].fillna(0).astype(int)

    # Conta tag totali per candidato (0, 1, o 2)
    result['dei_tag_count'] = result[existing_tag_cols].sum(axis=1)

    return result


def compute_dei_score(features: pd.DataFrame, config: DEIConfig) -> pd.DataFrame:
    """Calcola uno score DEI basato sui tag e target."""
    result = features.copy()

    # Score DEI = numero di tag * boost
    result['dei_boost'] = result['dei_tag_count'] * config.TAG_BOOST

    # Score combinato (cosine + dei boost)
    result['score_with_dei'] = result['cosine_similarity_normalized'] + result['dei_boost']

    # Clamp a [0, 1]
    result['score_with_dei'] = result['score_with_dei'].clip(0, 1)

    return result


def rerank_with_dei(features: pd.DataFrame) -> pd.DataFrame:
    """Ricalcola il rank per ogni JD usando lo score con DEI."""
    result = features.copy()

    # Rank originale (per confronto)
    result['rank_original'] = result['retrieval_rank']

    # Nuovo rank basato su score_with_dei (decrescente)
    result['rank_with_dei'] = result.groupby('jd_id')['score_with_dei'].rank(
        method='first', ascending=False
    ).astype(int)

    # Delta rank (positivo = salito in classifica)
    result['rank_delta'] = result['rank_original'] - result['rank_with_dei']

    return result


def build_dei_adjusted_features(config: DEIConfig) -> pd.DataFrame:
    features, cv_data, _ = load_dei_data(config)

    # Aggiungi tag DEI
    features = add_dei_tags(features, cv_data)

    # Calcola score con DEI
    features = compute_dei_score(features, config)

    # Ricalcola rank
    features = rerank_with_dei(features)

    # Ordina per jd_id e nuovo rank
    features = features.sort_values(['jd_id', 'rank_with_dei'])

    # Salva
    Path(config.OUTPUT_PATH).parent.mkdir(parents=True, exist_ok=True)
    features.to_csv(config.OUTPUT_PATH, index=False)

    # Stats
    moved = (features['rank_delta'] != 0).sum()
    moved_up = (features['rank_delta'] > 0).sum()
    moved_down = (features['rank_delta'] < 0).sum()

    print(f"Output: {config.OUTPUT_PATH}")
    print(f"Candidates with tags: {(features['dei_tag_count'] > 0).sum()}/{len(features)}")
    print(f"Rank changes: {moved} ({moved_up} up, {moved_down} down)")

    return features


# =============================================================================
# RERANKER - LINEAR MODEL + JSON OUTPUT
# Modello lineare per scoring finale e generazione output JSON stabile.
# =============================================================================

@dataclass
class LinearConfig:
    FEATURES_INPUT_PATH: str = "rerank_results/reranker_features.csv"
    OUTPUT_JSON_PATH: str = "rerank_results/rerank_output.json"

    # Pesi del modello lineare
    # Positivi = boost, Negativi = penalita
    # Somma pesi positivi ~ 1.0 per score interpretabile
    WEIGHTS: dict = None

    def __post_init__(self):
        self.WEIGHTS = {
            # Similarita semantica (peso principale)
            'cosine_similarity_normalized': 0.30,

            # Competenze (totale ~0.25)
            'skill_overlap_core_norm': 0.15,
            'skill_coverage_total': 0.05,
            'skill_overlap_nice_norm': 0.05,

            # Esperienza (totale ~0.20)
            'experience_meets_requirement': 0.15,
            'experience_bonus': 0.05,  # NUOVO: bonus per esperienza extra

            # Seniority (totale ~0.15)
            'seniority_match': 0.15,

            # Ruolo (totale ~0.10)
            'role_similarity_jaccard': 0.05,
            'role_coherent': 0.05,

            # Penalita
            'must_have_missing': -0.05,
            'experience_penalty_soft': -0.10,
            'experience_significantly_under': -0.10,  # NUOVO: penalità forte se mancano 2+ anni
            'seniority_mismatch_strong': -0.15,
            'seniority_underskilled': -0.05,
        }


linear_config = LinearConfig()


def load_features(config: LinearConfig) -> pd.DataFrame:
    df = pd.read_csv(config.FEATURES_INPUT_PATH)
    print(f"Loaded: {len(df)} candidate-JD pairs")
    return df


def compute_linear_score(df: pd.DataFrame, config: LinearConfig) -> pd.DataFrame:
    """Calcola lo score con modello lineare a pesi predefiniti."""
    result = df.copy()

    # Calcola score lineare e contributi per feature
    score = pd.Series(0.0, index=df.index)

    for feature, weight in config.WEIGHTS.items():
        if feature in df.columns:
            values = df[feature].fillna(0)
            contribution = weight * values
            result[f'contrib_{feature}'] = contribution
            score = score + contribution

    result['linear_score_raw'] = score

    # Normalizza in [0, 1] per ogni JD
    def normalize_group(group):
        min_val, max_val = group.min(), group.max()
        if max_val == min_val:
            return pd.Series(0.5, index=group.index)
        return (group - min_val) / (max_val - min_val)

    result['linear_score'] = result.groupby('jd_id')['linear_score_raw'].transform(normalize_group)

    # Applica DEI boost
    dei_boost = df['dei_boost'].fillna(0) if 'dei_boost' in df.columns else 0
    result['final_score'] = (result['linear_score'] + dei_boost).clip(0, 1)

    # Calcola rank finale
    result['final_rank'] = result.groupby('jd_id')['final_score'].rank(
        method='first', ascending=False
    ).astype(int)

    return result


def build_candidate_entry(row: pd.Series, config: LinearConfig) -> dict:
    """Costruisce l'entry JSON per un singolo candidato."""

    # Valori delle feature
    feature_values = {}
    for feature in config.WEIGHTS.keys():
        if feature in row.index:
            feature_values[feature] = round(float(row.get(feature, 0)), 4)

    # Contributi delle feature (peso × valore)
    feature_contributions = {}
    for feature in config.WEIGHTS.keys():
        contrib_col = f'contrib_{feature}'
        if contrib_col in row.index:
            feature_contributions[feature] = round(float(row.get(contrib_col, 0)), 4)

    return {
        'user_id': row['user_id'],
        'rank': int(row['final_rank']),
        'score': round(float(row['final_score']), 4),
        'score_breakdown': {
            'linear_score_raw': round(float(row.get('linear_score_raw', 0)), 4),
            'linear_score_normalized': round(float(row.get('linear_score', 0)), 4),
            'dei_boost': round(float(row.get('dei_boost', 0)), 4),
            'final_score': round(float(row['final_score']), 4)
        },
        'experience_details': {
            'cv_years': round(float(row.get('years_experience_cv', 0)), 1),
            'required_years': round(float(row.get('years_required_jd', 0)), 1),
            'gap': round(float(row.get('experience_gap', 0)), 1),
            'meets_requirement': bool(row.get('experience_meets_requirement', 0))
        },
        'feature_values': feature_values,
        'feature_contributions': feature_contributions,
        'flags': {
            'seniority_mismatch_strong': bool(row.get('seniority_mismatch_strong', 0)),
            'underskilled': bool(row.get('seniority_underskilled', 0)),
            'experience_below_requirement': bool(row.get('experience_meets_requirement', 1) == 0),
            'experience_significantly_under': bool(row.get('experience_significantly_under', 0)),
            'experience_overqualified': bool(row.get('experience_overqualified', 0)),
            'has_dei_tag': bool(row.get('dei_tag_count', 0) > 0)
        },
        'dei_tags': {
            'women': bool(row.get('tag_women', 0)),
            'protected_category': bool(row.get('tag_protected_category', 0))
        }
    }


def build_jd_entry(jd_id: str, jd_df: pd.DataFrame, config: LinearConfig) -> dict:
    """Costruisce l'entry JSON per una singola JD con tutti i candidati."""
    # Ordina per rank finale
    jd_df = jd_df.sort_values('final_rank')

    candidates = [build_candidate_entry(row, config) for _, row in jd_df.iterrows()]

    return {
        'jd_id': jd_id,
        'total_candidates': len(candidates),
        'candidates': candidates
    }


def build_output_json(df: pd.DataFrame, config: LinearConfig) -> dict:
    """Costruisce l'output JSON completo."""
    from datetime import datetime
    
    output = {
        'metadata': {
            'generated_at': datetime.now().isoformat(),
            'total_jds': df['jd_id'].nunique(),
            'total_candidates': len(df),
            'scoring_method': 'linear_weighted_model',
            'version': '1.1',  # Aggiornato per riflettere le modifiche
            'weights': config.WEIGHTS,
            'notes': 'Uses min_experience_years_normalized for experience comparison'
        },
        'results': []
    }

    for jd_id in df['jd_id'].unique():
        jd_df = df[df['jd_id'] == jd_id]
        output['results'].append(build_jd_entry(jd_id, jd_df, config))

    return output


def run_reranker(config: LinearConfig) -> dict:
    import json
    
    # Carica feature
    df = load_features(config)

    # Calcola score con modello lineare
    df = compute_linear_score(df, config)

    # Costruisci JSON
    output = build_output_json(df, config)

    # Salva JSON
    Path(config.OUTPUT_JSON_PATH).parent.mkdir(parents=True, exist_ok=True)
    with open(config.OUTPUT_JSON_PATH, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)

    print(f"Output: {config.OUTPUT_JSON_PATH}")
    print(f"JDs: {output['metadata']['total_jds']}, Candidates: {output['metadata']['total_candidates']}")

    return output


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def run_full_pipeline():
    """Esegue l'intera pipeline di reranking."""
    print("="*60)
    print("RERANKER PIPELINE")
    print("="*60)
    
    # Step 1: Feature Engineering
    print("\n[1/3] Feature Engineering")
    print("-"*40)
    features_df = build_all_features(config)
    
    # Step 2: DEI Adjustment
    print("\n[2/3] DEI Tag Adjustment")
    print("-"*40)
    features_df = build_dei_adjusted_features(dei_config)
    
    # Step 3: Linear Model & JSON Output
    print("\n[3/3] Linear Model Scoring")
    print("-"*40)
    output = run_reranker(linear_config)
    
    print("\n" + "="*60)
    print("PIPELINE COMPLETED")
    print("="*60)
    
    return output


if __name__ == "__main__":
    # Per eseguire solo il feature engineering:
    # features_df = build_all_features(config)
    
    # Per eseguire l'intera pipeline:
    run_full_pipeline()
