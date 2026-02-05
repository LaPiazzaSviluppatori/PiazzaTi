"""
XAI Builder - Explainable AI Module for CV-JD Matching
======================================================

Genera spiegazioni deterministiche e interpretabili per i risultati del matching.
Non usa LLM: tutte le spiegazioni derivano direttamente dalle feature e dai pesi del modello.

INPUT:  rerank_results/rerank_output.json (output del reranker)
OUTPUT: xai_output/xai_YYYY-MM-DD_HH-MM-SS.json

AGGIORNAMENTO v1.2:
- must_have_missing peso aggiornato da -0.075 a -0.10 (allineato a reranker v1.4)
- Rimosso linear_score_normalized da score_breakdown (coerente con reranker v1.3+)
- score_breakdown ora contiene: linear_score_raw, dei_boost, final_score
- Quality labels basati su final_score (= raw + dei_boost) che ora è assoluto

Uso da riga di comando:
    python xai_builder.py

Uso come modulo:
    from xai_builder import build_xai_company, build_xai_batch, run_xai_pipeline
"""

import json
from pathlib import Path
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime


# ============================================================================
# CONFIGURAZIONE
# ============================================================================

@dataclass
class XAIConfig:
    """Configurazione per il modulo XAI."""
    RERANKER_OUTPUT_PATH: str = "rerank_results/rerank_output.json"
    OUTPUT_DIR: str = "xai_output"

    # Pesi del modello (per reference nei metadata) - v1.4: must_have_missing aggiornato
    MODEL_WEIGHTS: Dict[str, float] = field(default_factory=lambda: {
        'cosine_similarity_normalized': 0.45,
        'skill_overlap_core_norm': 0.30,
        'skill_coverage_total': 0.15,
        'skill_overlap_nice_norm': 0.075,
        'experience_meets_requirement': 0.30,
        'seniority_match': 0.075,
        'role_similarity_jaccard': 0.10,
        'role_coherent': 0.10,
        'must_have_missing': -0.10,              # era -0.075 in v1.1
        'experience_penalty_soft': -0.15,
        'seniority_mismatch_strong': -0.225,
        'seniority_underskilled': -0.075,
    })


DEFAULT_CONFIG = XAIConfig()


# ============================================================================
# CONFIGURAZIONE SOGLIE
# ============================================================================

@dataclass
class XAIThresholds:
    """
    Soglie per la generazione delle spiegazioni.
    Calibrate per i pesi v1.2 del modello.
    """
    COSINE_STRONG: float = 0.65
    COSINE_MODERATE: float = 0.45
    SKILL_CORE_STRONG: float = 0.6
    SKILL_CORE_PARTIAL: float = 0.2
    SKILL_NICE_THRESHOLD: float = 0.25
    ROLE_SIMILARITY_MIN: float = 0.2
    MISSING_SKILLS_HIGH: int = 2
    EXPERIENCE_GAP_HIGH: float = 1.5


DEFAULT_THRESHOLDS = XAIThresholds()


# ============================================================================
# TEMPLATE TESTUALI
# ============================================================================

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
    "overskilled": "Seniority superiore - potrebbe essere overqualified",
}


# ============================================================================
# FUNZIONI CORE
# ============================================================================

def build_top_reasons(
    feature_values: Dict[str, float],
    feature_contributions: Dict[str, float],
    details: Dict[str, Any],
    experience_details: Optional[Dict[str, Any]] = None,
    seniority_details: Optional[Dict[str, Any]] = None,
    skills_details: Optional[Dict[str, Any]] = None,
    thresholds: XAIThresholds = DEFAULT_THRESHOLDS
) -> List[Dict[str, Any]]:
    """
    Genera i top motivi positivi per il match.
    Logica deterministica: per ogni feature sopra soglia, viene generato un motivo.
    Ordinati per contributo decrescente, max 5.
    """
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

    # 2. CORE SKILLS OVERLAP
    skill_core_val = feature_values.get('skill_overlap_core_norm', 0)
    skill_core_contrib = feature_contributions.get('skill_overlap_core_norm', 0)

    if skills_details:
        matched = skills_details.get('cv_skills_matched', 0)
        plural = "i" if matched != 1 else "e"
        skill_evidence = f"{matched} skill core present{plural}"
    else:
        skill_evidence = "N/A"

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

    if skills_details:
        nice_matched = skills_details.get('nice_to_have_matched', 0)
        nice_evidence = f"{nice_matched} skill nice-to-have presenti"
    else:
        nice_matched = 0
        nice_evidence = "N/A"

    if skill_nice_val >= thresholds.SKILL_NICE_THRESHOLD and nice_matched > 0:
        reasons.append({
            "reason_id": "nice_skills_present",
            "category": "skills",
            "text": REASON_TEMPLATES["nice_skills_present"],
            "contribution": round(skill_nice_contrib, 4),
            "evidence": nice_evidence
        })

    # 4. EXPERIENCE
    exp_meets = feature_values.get('experience_meets_requirement', 0)
    exp_contrib = feature_contributions.get('experience_meets_requirement', 0)

    if experience_details:
        years_cv = experience_details.get('cv_years', 0)
        years_jd = experience_details.get('required_years', 0)
    else:
        years_cv = details.get('years_experience_cv', 0)
        years_jd = details.get('years_required_jd', 0)

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

    # 5. SENIORITY MATCH
    seniority_match = feature_values.get('seniority_match', 0)
    seniority_contrib = feature_contributions.get('seniority_match', 0)

    if seniority_details:
        seniority_cv = seniority_details.get('cv_seniority', '')
        seniority_jd = seniority_details.get('required_seniority', '')
        seniority_gap = seniority_details.get('gap', 0)
    else:
        seniority_cv = details.get('seniority_cv', '')
        seniority_jd = details.get('seniority_jd', '')
        seniority_gap = 0

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

    reasons.sort(key=lambda x: x['contribution'], reverse=True)
    return reasons[:5]


def build_main_risks(
    feature_values: Dict[str, float],
    feature_contributions: Dict[str, float],
    details: Dict[str, Any],
    experience_details: Optional[Dict[str, Any]] = None,
    seniority_details: Optional[Dict[str, Any]] = None,
    skills_details: Optional[Dict[str, Any]] = None,
    thresholds: XAIThresholds = DEFAULT_THRESHOLDS
) -> List[Dict[str, Any]]:
    """
    Genera i principali rischi/gap del match.
    Ordinati per severità e impatto, max 3.
    """
    risks = []

    # 1. MUST-HAVE SKILLS MANCANTI
    must_have_missing = feature_values.get('must_have_missing', 0)
    must_have_contrib = feature_contributions.get('must_have_missing', 0)

    if must_have_missing > 0:
        if skills_details:
            missing_count = skills_details.get('must_have_missing', int(must_have_missing))
        else:
            missing_count = int(must_have_missing)

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

    # 2. STRONG SENIORITY MISMATCH
    seniority_mismatch = feature_values.get('seniority_mismatch_strong', 0)
    seniority_mismatch_contrib = feature_contributions.get('seniority_mismatch_strong', 0)

    if seniority_details:
        seniority_cv = seniority_details.get('cv_seniority', '')
        seniority_jd = seniority_details.get('required_seniority', '')
    else:
        seniority_cv = details.get('seniority_cv', '')
        seniority_jd = details.get('seniority_jd', '')

    if seniority_mismatch == 1.0:
        if seniority_cv and seniority_jd:
            seniority_evidence = f"Candidato: {seniority_cv}, richiesta: {seniority_jd}"
        else:
            seniority_evidence = "Gap di 2+ livelli"

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
        if seniority_cv and seniority_jd:
            underskilled_evidence = f"Candidato: {seniority_cv}, richiesta: {seniority_jd}"
        else:
            underskilled_evidence = "Seniority insufficiente"

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
    exp_penalty = feature_values.get('experience_penalty_soft', 0)
    exp_penalty_contrib = feature_contributions.get('experience_penalty_soft', 0)

    if experience_details:
        years_cv = experience_details.get('cv_years', 0)
        years_jd = experience_details.get('required_years', 0)
    else:
        years_cv = details.get('years_experience_cv', 0)
        years_jd = details.get('years_required_jd', 0)

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

    severity_order = {"high": 0, "medium": 1, "low": 2}
    risks.sort(key=lambda x: (severity_order.get(x['severity'], 2), x['contribution']))

    return risks[:3]


def build_evidence_summary(
    feature_values: Dict[str, float],
    details: Dict[str, Any],
    experience_details: Optional[Dict[str, Any]] = None,
    seniority_details: Optional[Dict[str, Any]] = None,
    skills_details: Optional[Dict[str, Any]] = None
) -> Dict[str, Any]:
    """Costruisce un riepilogo delle evidenze concrete."""
    if skills_details:
        skills_matched = skills_details.get('cv_skills_matched', 0)
        skills_required = skills_details.get('jd_skills_required', 0)
        skills_missing = skills_details.get('must_have_missing', 0)
        nice_matched = skills_details.get('nice_to_have_matched', 0)
        nice_total = skills_details.get('nice_to_have_total', 0)
    else:
        skills_matched = len(details.get('skills_matched', []))
        skills_required = len(details.get('jd_requirements', []))
        skills_missing = skills_required - skills_matched
        nice_matched = len(details.get('skills_nice_matched', []))
        nice_total = len(details.get('jd_nice_to_have', []))

    if experience_details:
        years_cv = experience_details.get('cv_years', 0)
        years_jd = experience_details.get('required_years', 0)
        experience_gap = experience_details.get('gap', years_cv - years_jd)
    else:
        years_cv = details.get('years_experience_cv', 0)
        years_jd = details.get('years_required_jd', 0)
        experience_gap = years_cv - years_jd

    if seniority_details:
        seniority_cv = seniority_details.get('cv_seniority', '')
        seniority_jd = seniority_details.get('required_seniority', '')
        seniority_gap = seniority_details.get('gap', 0)
    else:
        seniority_cv = details.get('seniority_cv', '')
        seniority_jd = details.get('seniority_jd', '')
        seniority_levels = {'junior': 1, 'mid': 2, 'senior': 3}
        cv_level = seniority_levels.get(str(seniority_cv).lower(), 0)
        jd_level = seniority_levels.get(str(seniority_jd).lower(), 0)
        seniority_gap = cv_level - jd_level

    return {
        "skills_core_matched": skills_matched,
        "skills_core_required": skills_required,
        "skills_core_missing": skills_missing,
        "skills_nice_matched": nice_matched,
        "skills_nice_total": nice_total,
        "cv_current_role": details.get('cv_current_role', ''),
        "experience_cv_years": int(round(years_cv)),
        "experience_jd_required": int(round(years_jd)),
        "experience_gap": int(round(experience_gap)),
        "seniority_cv": seniority_cv,
        "seniority_jd": seniority_jd,
        "seniority_gap": seniority_gap,
        "cv_completeness": details.get('cv_completeness_score', 0)
    }


# ============================================================================
# FUNZIONI PUBBLICHE (API del modulo)
# ============================================================================

def build_xai_company(
    candidate_data: Dict[str, Any],
    details: Optional[Dict[str, Any]] = None,
    jd_info: Optional[Dict[str, Any]] = None,
    thresholds: XAIThresholds = DEFAULT_THRESHOLDS
) -> Dict[str, Any]:
    """
    Costruisce l'output XAI completo per un singolo candidato (Company View).
    
    v1.2: score_breakdown non contiene più linear_score_normalized.
    Pesi aggiornati con must_have_missing = -0.10.
    """
    feature_values = candidate_data.get('feature_values', {})
    feature_contributions = candidate_data.get('feature_contributions', {})
    score_breakdown = candidate_data.get('score_breakdown', {})

    experience_details = candidate_data.get('experience_details', None)
    seniority_details = candidate_data.get('seniority_details', None)
    skills_details = candidate_data.get('skills_details', None)

    if details is None:
        details = candidate_data.get('details', {})

    # Recupera cv_completeness_score da parsing_quality se non presente in details
    # (nel flusso batch il reranker lo mette in parsing_quality, nel flusso singolo è già in details)
    if 'cv_completeness_score' not in details:
        parsing_quality = candidate_data.get('parsing_quality', {})
        if 'cv_completeness_score' in parsing_quality:
            details['cv_completeness_score'] = parsing_quality['cv_completeness_score']

    top_reasons = build_top_reasons(
        feature_values, feature_contributions, details,
        experience_details, seniority_details, skills_details, thresholds
    )
    main_risks = build_main_risks(
        feature_values, feature_contributions, details,
        experience_details, seniority_details, skills_details, thresholds
    )
    evidence = build_evidence_summary(
        feature_values, details,
        experience_details, seniority_details, skills_details
    )

    final_score = candidate_data.get('score', 0)
    if final_score >= 0.45:
        quality_label = "EXCELLENT"
    elif final_score >= 0.20:
        quality_label = "GOOD"
    else:
        quality_label = "WEAK"

    xai_output = {
        "xai_version": "1.2",
        "generated_at": datetime.now().isoformat(),
        "view_type": "company",

        "match_summary": {
            "user_id": candidate_data.get('user_id', ''),
            "jd_id": jd_info.get('jd_id', '') if jd_info else '',
            "jd_title": jd_info.get('title', '') if jd_info else '',
            "final_score": round(final_score, 4),
            "quality_label": quality_label,
            "rank": candidate_data.get('rank', 0)
        },

        "score_breakdown": {
            "linear_score_raw": score_breakdown.get('linear_score_raw', 0),
            "dei_boost": score_breakdown.get('dei_boost', 0),
            "final_score": score_breakdown.get('final_score', 0)
        },

        "explanation": {
            "top_reasons": top_reasons,
            "main_risks": main_risks,
            "candidate_actions": []
        },

        "feature_details": {
            "values": feature_values,
            "contributions": feature_contributions
        },

        "evidence": evidence,

        "flags": candidate_data.get('flags', {}),
        "dei_tags": candidate_data.get('dei_tags', {})
    }

    return xai_output


def build_xai_batch(
    candidates: List[Dict[str, Any]],
    jd_info: Dict[str, Any],
    thresholds: XAIThresholds = DEFAULT_THRESHOLDS
) -> Dict[str, Any]:
    """
    Costruisce l'output XAI per un batch di candidati (top N per una JD).
    """
    candidates_xai = []

    for candidate in candidates:
        details = candidate.get('details', {})
        xai = build_xai_company(candidate, details, jd_info, thresholds)
        candidates_xai.append(xai)

    return {
        "metadata": {
            "generated_at": datetime.now().isoformat(),
            "xai_version": "1.2",
            "view_type": "company_batch",
            "total_candidates": len(candidates_xai),
            "jd_id": jd_info.get('jd_id', ''),
            "thresholds": {
                "cosine_strong": thresholds.COSINE_STRONG,
                "cosine_moderate": thresholds.COSINE_MODERATE,
                "skill_core_strong": thresholds.SKILL_CORE_STRONG,
                "skill_core_partial": thresholds.SKILL_CORE_PARTIAL,
                "missing_skills_high": thresholds.MISSING_SKILLS_HIGH,
                "experience_gap_high": thresholds.EXPERIENCE_GAP_HIGH
            }
        },
        "jd_info": jd_info,
        "candidates_xai": candidates_xai
    }


def enrich_reranker_output(
    reranker_output: Dict[str, Any],
    thresholds: XAIThresholds = DEFAULT_THRESHOLDS
) -> Dict[str, Any]:
    """
    Arricchisce l'output completo del reranker con le spiegazioni XAI.
    """
    enriched = reranker_output.copy()
    enriched['metadata']['xai_version'] = "1.2"
    enriched['metadata']['xai_generated_at'] = datetime.now().isoformat()

    for jd_result in enriched.get('results', []):
        jd_info = {
            'jd_id': jd_result.get('jd_id', ''),
            'title': jd_result.get('title', '')
        }

        for candidate in jd_result.get('candidates', []):
            details = candidate.get('details', {})
            xai = build_xai_company(candidate, details, jd_info, thresholds)

            candidate['xai'] = {
                "top_reasons": xai['explanation']['top_reasons'],
                "main_risks": xai['explanation']['main_risks'],
                "evidence": xai['evidence'],
                "quality_label": xai['match_summary']['quality_label']
            }

    return enriched


# ============================================================================
# UTILITY: Verifica coerenza score
# ============================================================================

def verify_score_consistency(
    feature_contributions: Dict[str, float],
    score_breakdown: Dict[str, float],
    tolerance: float = 0.01
) -> Dict[str, Any]:
    """
    Verifica che la somma dei contributi ricostruisca lo score.
    
    Con la rimozione della normalizzazione (v1.3 reranker), la somma dei
    contributi corrisponde direttamente a linear_score_raw, senza
    passaggi intermedi che rompevano la tracciabilità.
    """
    sum_contributions = sum(feature_contributions.values())
    linear_score_raw = score_breakdown.get('linear_score_raw', 0)
    difference = abs(sum_contributions - linear_score_raw)

    return {
        "is_consistent": difference <= tolerance,
        "sum_contributions": round(sum_contributions, 4),
        "linear_score_raw": round(linear_score_raw, 4),
        "difference": round(difference, 4)
    }


# ============================================================================
# PIPELINE PRINCIPALE
# ============================================================================

def load_reranker_output(config: XAIConfig = DEFAULT_CONFIG) -> Dict[str, Any]:
    """Carica l'output del reranker da file JSON."""
    input_path = Path(config.RERANKER_OUTPUT_PATH)

    if not input_path.exists():
        raise FileNotFoundError(f"File reranker non trovato: {input_path}")

    with open(input_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"Loaded: {input_path}")
    print(f"  - JDs: {data.get('metadata', {}).get('total_jds', 'N/A')}")
    print(f"  - Candidates: {data.get('metadata', {}).get('total_candidates', 'N/A')}")

    return data


def generate_output_filename() -> str:
    """Genera il nome del file di output con timestamp."""
    timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    return f"xai_{timestamp}.json"


def process_reranker_output(
    reranker_output: Dict[str, Any],
    thresholds: XAIThresholds = DEFAULT_THRESHOLDS
) -> Dict[str, Any]:
    """Processa l'output del reranker e genera le spiegazioni XAI."""
    original_metadata = reranker_output.get('metadata', {})

    total_jds = len(reranker_output.get('results', []))
    total_candidates = sum(
        len(jd_result.get('candidates', []))
        for jd_result in reranker_output.get('results', [])
    )

    metadata = {
        "generated_at": datetime.now().isoformat(),
        "xai_version": "1.2",
        "total_jds": total_jds,
        "total_candidates": total_candidates,
        "source_file": original_metadata.get('generated_at', 'unknown'),
        "scoring_method": original_metadata.get('scoring_method', 'linear_weighted_model'),
        "model_weights": original_metadata.get('weights', {}),
        "notes": "v1.2: Compatible with reranker v1.4 (must_have_missing=-0.10, no group normalization)",
        "thresholds": {
            "cosine_strong": thresholds.COSINE_STRONG,
            "cosine_moderate": thresholds.COSINE_MODERATE,
            "skill_core_strong": thresholds.SKILL_CORE_STRONG,
            "skill_core_partial": thresholds.SKILL_CORE_PARTIAL,
            "skill_nice_threshold": thresholds.SKILL_NICE_THRESHOLD,
            "missing_skills_high": thresholds.MISSING_SKILLS_HIGH,
            "experience_gap_high": thresholds.EXPERIENCE_GAP_HIGH
        }
    }

    results = []

    for jd_result in reranker_output.get('results', []):
        jd_id = jd_result.get('jd_id', '')
        jd_title = jd_result.get('title', '')

        jd_info = {
            'jd_id': jd_id,
            'title': jd_title
        }

        candidates_with_xai = []

        for candidate in jd_result.get('candidates', []):
            details = candidate.get('details', {})
            xai = build_xai_company(candidate, details, jd_info, thresholds)

            candidate_with_xai = candidate.copy()
            candidate_with_xai['xai'] = {
                "quality_label": xai['match_summary']['quality_label'],
                "top_reasons": xai['explanation']['top_reasons'],
                "main_risks": xai['explanation']['main_risks'],
                "evidence": xai['evidence']
            }

            candidates_with_xai.append(candidate_with_xai)

        results.append({
            "jd_id": jd_id,
            "jd_title": jd_title,
            "total_candidates": len(candidates_with_xai),
            "candidates": candidates_with_xai
        })

    return {
        "metadata": metadata,
        "results": results
    }


def save_xai_output(
    xai_output: Dict[str, Any],
    config: XAIConfig = DEFAULT_CONFIG
) -> Path:
    """Salva l'output XAI su file JSON."""
    output_dir = Path(config.OUTPUT_DIR)
    output_dir.mkdir(parents=True, exist_ok=True)

    filename = generate_output_filename()
    output_path = output_dir / filename

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(xai_output, f, indent=2, ensure_ascii=False)

    print(f"\nOutput saved: {output_path}")

    return output_path


def run_xai_pipeline(
    config: XAIConfig = DEFAULT_CONFIG,
    thresholds: XAIThresholds = DEFAULT_THRESHOLDS
) -> Path:
    """
    Esegue la pipeline XAI completa:
    1. Carica output reranker
    2. Genera spiegazioni per tutti i candidati
    3. Salva output in xai_output/
    """
    print("=" * 60)
    print("XAI BUILDER v1.2 - Processing Reranker Output")
    print("=" * 60)

    print("\n[1/3] Loading reranker output...")
    reranker_output = load_reranker_output(config)

    print("\n[2/3] Generating XAI explanations...")
    xai_output = process_reranker_output(reranker_output, thresholds)

    total_reasons = sum(
        len(c.get('xai', {}).get('top_reasons', []))
        for r in xai_output['results']
        for c in r['candidates']
    )
    total_risks = sum(
        len(c.get('xai', {}).get('main_risks', []))
        for r in xai_output['results']
        for c in r['candidates']
    )

    print(f"  - Generated {total_reasons} reasons")
    print(f"  - Generated {total_risks} risks")

    print("\n[3/3] Saving output...")
    output_path = save_xai_output(xai_output, config)

    print("\n" + "=" * 60)
    print("XAI PIPELINE COMPLETED")
    print("=" * 60)

    return output_path


# ============================================================================
# MAIN
# ============================================================================

if __name__ == "__main__":
    try:
        output_path = run_xai_pipeline()
        print(f"\nSuccess! Output: {output_path}")
    except FileNotFoundError as e:
        print(f"\nError: {e}")
        print("Make sure to run the reranker first to generate rerank_results/rerank_output.json")
    except Exception as e:
        print(f"\nUnexpected error: {e}")
        raise
