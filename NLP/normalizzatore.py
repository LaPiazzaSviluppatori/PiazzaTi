# -*- coding: utf-8 -*-
"""
Script di Normalizzazione Dataset CV e JD
Calcola seniority da anni di esperienza reali invece che da keyword nei titoli.
Normalizza salary in formato leggibile e gestisce tag DE&I.

CHANGELOG:
- v3: Aggiunto supporto per campo company_name nelle JD
- v2: Aggiunto supporto per campo min_experience_years nelle JD
- v1: Versione iniziale
"""

import json
import pandas as pd
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
from dateutil import parser
from collections import defaultdict

# ============================================================================
# CONFIGURAZIONE
# ============================================================================

DATASET_DIR = Path("Dataset")
INPUT_CV = DATASET_DIR / "cv_dataset.csv"
INPUT_JD = DATASET_DIR / "jd_dataset.csv"
ONTOLOGY_FILE = DATASET_DIR / "skill_ontology.json"

OUTPUT_DIR = DATASET_DIR / "normalized"
OUTPUT_CV = OUTPUT_DIR / "cv_dataset_normalized.csv"
OUTPUT_JD = OUTPUT_DIR / "jd_dataset_normalized.csv"

# Configurazione per min_experience_years
MIN_EXP_YEARS_DEFAULT = 2  # Valore di default se mancante
MIN_EXP_YEARS_RANGE = (1, 10)  # Range valido (min, max)

# Mappatura seniority -> anni di esperienza di default
SENIORITY_TO_YEARS = {
    "junior": 1,
    "mid": 3,
    "senior": 5
}

# ============================================================================
# CARICAMENTO ONTOLOGIA
# ============================================================================

class SkillOntology:
    """
    Gestisce l'ontologia delle skill per la normalizzazione.
    
    Scopo: Fornire mappature consistenti per:
    - Skills tecniche (es. "js" → "JavaScript")
    - Livelli seniority (es. "sr." → "senior")
    - Livelli linguistici CEFR (es. "native" → "C2")
    
    L'ontologia viene aggiornata automaticamente con le skill non mappate
    trovate durante il processing, facilitando il mantenimento.
    """

    def __init__(self, ontology_path: Path):
        print(f"Caricamento ontologia da: {ontology_path}")
        self.ontology_path = ontology_path

        with open(ontology_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        self.skill_mappings = self.data.get('skill_mappings', {})
        self.seniority_mappings = self.data.get('seniority_mappings', {})
        self.cefr_mappings = self.data.get('cefr_mappings', {})
        self.metadata = self.data.get('_metadata', {})

        # Rimuovi commenti (chiavi che iniziano con _)
        self.skill_mappings = {k: v for k, v in self.skill_mappings.items()
                               if not k.startswith('_')}
        self.seniority_mappings = {k: v for k, v in self.seniority_mappings.items()
                                   if not k.startswith('_')}
        self.cefr_mappings = {k: v for k, v in self.cefr_mappings.items()
                              if not k.startswith('_')}

        self.unmapped_skills = defaultdict(int)
        previous_unmapped = self.data.get('unmapped_skills', {}).get('skills', [])
        self.previous_unmapped = {item['skill'] for item in previous_unmapped}

        print(f"  Mappature skill: {len(self.skill_mappings)}")
        print(f"  Mappature seniority: {len(self.seniority_mappings)}")
        print(f"  Mappature CEFR: {len(self.cefr_mappings)}")
        if self.previous_unmapped:
            print(f"  Skill da mappare: {len(self.previous_unmapped)}")
        print()

    def normalize_skill(self, skill: str) -> str:
        """
        Normalizza una singola skill usando l'ontologia.
        
        Esempio: "js" → "JavaScript", "ml" → "Machine Learning"
        """
        if not skill or pd.isna(skill):
            return ""

        skill_clean = skill.strip()
        skill_lower = skill_clean.lower()

        if skill_lower in self.skill_mappings:
            return self.skill_mappings[skill_lower]

        if skill_clean not in self.previous_unmapped:
            self.unmapped_skills[skill_clean] += 1

        return skill_clean.capitalize()

    def normalize_seniority(self, seniority_str: str) -> str:
        """
        Normalizza il livello di seniority.
        
        Converte varianti come "sr.", "senior level", "5+ years" in
        valori standard: "junior", "mid", "senior".
        """
        if not seniority_str or pd.isna(seniority_str):
            return "mid"

        sen_lower = seniority_str.lower().strip()

        for keyword, level in self.seniority_mappings.items():
            if keyword in sen_lower:
                return level

        years_match = re.search(r'(\d+)\+?\s*(years|anni)', sen_lower)
        if years_match:
            years = int(years_match.group(1))
            return self._years_to_seniority(years)

        return "mid"

    def normalize_cefr(self, level_str: str) -> str:
        """
        Normalizza il livello linguistico in formato CEFR.
        
        Esempio: "native" → "C2", "fluent" → "C1", "intermediate" → "B1"
        """
        if not level_str or pd.isna(level_str):
            return "B2"

        level_lower = level_str.lower().strip()

        if level_lower in self.cefr_mappings:
            return self.cefr_mappings[level_lower]

        return "B2"

    def _years_to_seniority(self, years: float) -> str:
        """Converte anni di esperienza in livello seniority."""
        if years < 2.0:
            return "junior"
        elif years < 5.0:
            return "mid"
        else:
            return "senior"

    def save_updated_ontology(self):
        """
        Salva l'ontologia aggiornata con le nuove skill non mappate.
        
        Questo permette di identificare facilmente quali skill
        necessitano di essere aggiunte alle mappature.
        """
        print(f"\nAggiornamento ontologia...")

        new_unmapped = [
            {
                "skill": skill,
                "frequency": freq,
                "suggested_canonical": skill.capitalize()
            }
            for skill, freq in sorted(self.unmapped_skills.items(),
                                     key=lambda x: x[1], reverse=True)
        ]

        existing_unmapped = self.data.get('unmapped_skills', {}).get('skills', [])
        existing_skills = {item['skill'] for item in existing_unmapped}

        for item in new_unmapped:
            if item['skill'] not in existing_skills:
                existing_unmapped.append(item)

        existing_unmapped.sort(key=lambda x: x['frequency'], reverse=True)

        self.data['_metadata'] = {
            **self.metadata,
            "last_updated": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "total_mappings": len(self.skill_mappings),
            "unmapped_skills_count": len(existing_unmapped)
        }

        self.data['unmapped_skills'] = {
            "_comment": "Skill trovate nei dataset ma non ancora mappate",
            "skills": existing_unmapped
        }

        with open(self.ontology_path, 'w', encoding='utf-8') as f:
            json.dump(self.data, f, indent=2, ensure_ascii=False)

        print(f"  Aggiornata: {self.ontology_path}")
        print(f"  Skill non mappate: {len(existing_unmapped)}")

        if len(new_unmapped) > 0:
            print(f"  Nuove skill: {len(new_unmapped)}")
            print(f"\n  Top 10 skill da mappare:")
            for item in new_unmapped[:10]:
                print(f"    {item['skill']:35} (freq: {item['frequency']:3})")

        if len(existing_unmapped) > 0:
            print(f"\n  Azione richiesta: rivedi unmapped_skills in {self.ontology_path}")
        else:
            print(f"\n  Tutte le skill sono mappate")

        print()

# ============================================================================
# PARSING DATE
# ============================================================================

def parse_date_flexible(date_str: str) -> Optional[datetime]:
    """
    Parser flessibile per date in vari formati (IT/EN).
    
    Gestisce:
    - Date standard: "2023-01-15", "15/01/2023"
    - Mesi italiani: "gennaio 2023"
    - Valori speciali: "present", "current", "attuale"
    - Solo anno: "2023"
    """
    if not date_str or pd.isna(date_str):
        return None

    date_str = str(date_str).strip()

    if date_str.lower() in ['present', 'presente', 'current', 'attuale', 'now']:
        return datetime.now()

    month_map_it_en = {
        'gennaio': 'january', 'febbraio': 'february', 'marzo': 'march',
        'aprile': 'april', 'maggio': 'may', 'giugno': 'june',
        'luglio': 'july', 'agosto': 'august', 'settembre': 'september',
        'ottobre': 'october', 'novembre': 'november', 'dicembre': 'december'
    }

    date_str_lower = date_str.lower()
    for it_month, en_month in month_map_it_en.items():
        if it_month in date_str_lower:
            date_str = date_str_lower.replace(it_month, en_month)
            break

    try:
        parsed = parser.parse(date_str, fuzzy=True, default=datetime(2000, 1, 1))
        return parsed
    except:
        year_match = re.search(r'\b(19|20)\d{2}\b', date_str)
        if year_match:
            year = int(year_match.group(0))
            return datetime(year, 1, 1)
        return None

def calculate_years_of_experience(experience_str: str) -> float:
    """
    Calcola gli anni totali di esperienza da una stringa di esperienze.
    
    Input: "Data Scientist @ Company [2022-01 - 2024-05] | Junior Dev @ Startup [2020 - 2022]"
    Output: 4.3 (anni totali)
    """
    if not experience_str or pd.isna(experience_str):
        return 0.0

    date_pattern = r'\[(.*?)\]'
    experiences = experience_str.split('|')
    total_years = 0.0

    for exp in experiences:
        date_match = re.search(date_pattern, exp)
        if not date_match:
            continue

        date_range = date_match.group(1)
        parts = re.split(r'\s*[-–]\s*', date_range)
        if len(parts) != 2:
            continue

        start_str, end_str = parts
        start_date = parse_date_flexible(start_str)
        end_date = parse_date_flexible(end_str)

        if start_date and end_date:
            delta = end_date - start_date
            years = delta.days / 365.25
            total_years += max(0, years)

    return round(total_years, 1)

def infer_seniority_from_experience(experience_str: str) -> Tuple[str, float]:
    """
    Inferisce il livello di seniority dagli anni di esperienza reali.
    
    Questo è più affidabile che basarsi sui titoli (es. "Senior" nel titolo
    potrebbe non riflettere l'esperienza reale).
    
    Returns: (seniority_level, years_of_experience)
    """
    years = calculate_years_of_experience(experience_str)

    if years < 2.0:
        seniority = "junior"
    elif years < 5.0:
        seniority = "mid"
    else:
        seniority = "senior"

    return seniority, years

# ============================================================================
# FUNZIONI DI NORMALIZZAZIONE
# ============================================================================

def normalize_skills_string(skills_str: str, ontology: SkillOntology) -> str:
    """
    Normalizza una stringa di skills separate da virgola.
    
    Operazioni:
    1. Rimuove informazioni tra parentesi (es. "Python (Advanced)")
    2. Applica mappatura ontologia
    3. Rimuove duplicati preservando ordine
    """
    if not skills_str or pd.isna(skills_str):
        return ""

    skills_str = re.sub(r'\([^)]*\)', '', skills_str)
    skills = [ontology.normalize_skill(s.strip())
              for s in skills_str.split(',')
              if s.strip()]

    seen = set()
    unique_skills = []
    for skill in skills:
        if skill and skill not in seen:
            seen.add(skill)
            unique_skills.append(skill)

    return ", ".join(unique_skills)

def normalize_language(lang_str: str, ontology: SkillOntology) -> Tuple[str, str]:
    """
    Normalizza una singola lingua con livello.
    
    Input: "English (fluent)" o "italiano (madrelingua)"
    Output: ("English", "C1") o ("Italiano", "C2")
    """
    if not lang_str or pd.isna(lang_str):
        return ("", "")

    match = re.match(r'([^(]+)\(([^)]+)\)', lang_str.strip())
    if match:
        lang_name = match.group(1).strip().capitalize()
        level_raw = match.group(2).strip()
        level_normalized = ontology.normalize_cefr(level_raw)
        return (lang_name, level_normalized)

    return (lang_str.strip().capitalize(), "B2")

def normalize_languages_string(langs_str: str, ontology: SkillOntology) -> str:
    """
    Normalizza una stringa di lingue separate da virgola.
    
    Input: "English (fluent), Italian (native)"
    Output: "English (C1), Italian (C2)"
    """
    if not langs_str or pd.isna(langs_str):
        return ""

    langs = [s.strip() for s in langs_str.split(',') if s.strip()]
    normalized = []

    for lang in langs:
        lang_name, level = normalize_language(lang, ontology)
        if lang_name:
            normalized.append(f"{lang_name} ({level})")

    return ", ".join(normalized)

def extract_salary_range(salary_str: str) -> str:
    """
    Pulisce e normalizza una stringa di salary range.
    
    Rimuove parole vaghe come "circa", "about", "around".
    """
    if not salary_str or pd.isna(salary_str):
        return ""

    salary_clean = str(salary_str).strip()

    words_to_remove = ['circa', 'about', 'around', 'approximately']
    for word in words_to_remove:
        salary_clean = re.sub(rf'\b{word}\b', '', salary_clean, flags=re.IGNORECASE)

    salary_clean = re.sub(r'\s+', ' ', salary_clean).strip()

    return salary_clean


def normalize_min_experience_years(value, seniority: str = None) -> int:
    """
    Normalizza il campo min_experience_years.
    
    Logica di fallback:
    1. Se il valore è valido (numero nel range), lo usa
    2. Se mancante/invalido ma c'è seniority, inferisce da seniority
    3. Altrimenti usa il default (2 anni)
    
    Args:
        value: valore dal CSV (può essere int, float, str, NaN)
        seniority: livello seniority normalizzato (opzionale, per inferenza)
    
    Returns:
        int: anni di esperienza minimi (nel range 1-10)
    """
    # Caso 1: valore valido presente
    if pd.notna(value):
        try:
            years = int(float(value))
            # Verifica che sia nel range valido
            min_val, max_val = MIN_EXP_YEARS_RANGE
            if min_val <= years <= max_val:
                return years
            # Se fuori range, clamp al range valido
            return max(min_val, min(max_val, years))
        except (ValueError, TypeError):
            pass
    
    # Caso 2: inferisci da seniority se disponibile
    if seniority and seniority in SENIORITY_TO_YEARS:
        return SENIORITY_TO_YEARS[seniority]
    
    # Caso 3: usa default
    return MIN_EXP_YEARS_DEFAULT


def validate_seniority_experience_consistency(seniority: str, min_years: int) -> Tuple[bool, str]:
    """
    Verifica la coerenza tra seniority e anni di esperienza richiesti.
    
    Utile per identificare errori nei dati, es:
    - JD che richiede "senior" ma solo 1 anno di esperienza
    - JD che richiede "junior" ma 7 anni di esperienza
    
    Returns: (is_consistent, warning_message)
    """
    expected_ranges = {
        "junior": (0, 2),
        "mid": (2, 5),
        "senior": (5, 15)
    }
    
    if seniority not in expected_ranges:
        return True, ""
    
    min_expected, max_expected = expected_ranges[seniority]
    
    if min_years < min_expected:
        return False, f"seniority '{seniority}' con solo {min_years} anni richiesti (atteso >= {min_expected})"
    elif min_years > max_expected:
        return False, f"seniority '{seniority}' con {min_years} anni richiesti (atteso <= {max_expected})"
    
    return True, ""


def normalize_company_name(company_name: str) -> str:
    """
    Normalizza il nome dell'azienda.
    
    Operazioni:
    1. Strip whitespace
    2. Gestisce valori mancanti
    
    Il nome azienda non viene modificato sostanzialmente perché
    è un identificatore che deve rimanere riconoscibile.
    
    NUOVO in v3: Funzione aggiunta per gestione esplicita del campo company_name.
    """
    if not company_name or pd.isna(company_name):
        return ""
    
    return str(company_name).strip()


# ============================================================================
# NORMALIZZAZIONE DATASET
# ============================================================================

def normalize_cv_dataset(input_path: Path, output_path: Path, ontology: SkillOntology) -> pd.DataFrame:
    """
    Normalizza il dataset CV.
    
    Campi normalizzati:
    - skills → skills_normalized (mappatura ontologia)
    - languages → languages_normalized (formato CEFR)
    - experience → inferred_seniority + years_of_experience (calcolato da date)
    - pref_salary_expectation → pref_salary_normalized (pulizia)
    - tag_* → booleani True/None
    """
    print(f"\n{'='*80}")
    print(f"NORMALIZZAZIONE DATASET CV")
    print(f"{'='*80}\n")

    print(f"Caricamento: {input_path}")
    df = pd.read_csv(input_path)
    print(f"Righe caricate: {len(df)}\n")

    print("Normalizzazione skills...")
    df['skills_normalized'] = df['skills'].apply(
        lambda x: normalize_skills_string(x, ontology)
    )
    print(f"  Prima:  {df['skills'].iloc[0][:80]}...")
    print(f"  Dopo:   {df['skills_normalized'].iloc[0][:80]}...\n")

    print("Normalizzazione lingue...")
    df['languages_normalized'] = df['languages'].apply(
        lambda x: normalize_languages_string(x, ontology)
    )
    print(f"  Prima: {df['languages'].iloc[0]}")
    print(f"  Dopo:  {df['languages_normalized'].iloc[0]}\n")

    print("Calcolo seniority da anni di esperienza...")
    seniority_data = df['experience'].apply(infer_seniority_from_experience)
    df['inferred_seniority'] = seniority_data.apply(lambda x: x[0])
    df['years_of_experience'] = seniority_data.apply(lambda x: x[1])

    print(f"  Distribuzione seniority:")
    for level, count in df['inferred_seniority'].value_counts().items():
        avg_years = df[df['inferred_seniority'] == level]['years_of_experience'].mean()
        print(f"    {level:8} {count:3} ({count/len(df)*100:5.1f}%)  →  media {avg_years:.1f} anni")

    print(f"\n  Statistiche esperienza:")
    print(f"    Min:    {df['years_of_experience'].min():.1f} anni")
    print(f"    Media:  {df['years_of_experience'].mean():.1f} anni")
    print(f"    Max:    {df['years_of_experience'].max():.1f} anni")
    print()

    print("Normalizzazione salary...")
    df['pref_salary_normalized'] = df['pref_salary_expectation'].apply(extract_salary_range)

    valid = df[df['pref_salary_normalized'] != ""]
    print(f"  Normalizzati: {len(valid)}/{len(df)}")

    if len(valid) > 0:
        print(f"\n  Esempi:")
        for idx in valid.head(5).index:
            orig = df.loc[idx, 'pref_salary_expectation']
            norm = df.loc[idx, 'pref_salary_normalized']
            print(f"    {orig:30} → {norm}")
    print()

    print("Normalizzazione tags...")

    tag_columns = [col for col in df.columns if col.startswith('tag_')]

    if tag_columns:
        print(f"  Trovate {len(tag_columns)} colonne tag:")

        for tag_col in tag_columns:
            tag_name = tag_col.replace('tag_', '')
            df[tag_col] = df[tag_col].apply(lambda x: True if x is True else None)
            after_true = (df[tag_col] == True).sum()
            print(f"    {tag_name:25} {after_true:3} True, {len(df) - after_true:3} None")

        print(f"\n  Distribuzione candidati:")
        has_any_tag = df[tag_columns].any(axis=1).sum()
        print(f"    Con almeno 1 tag: {has_any_tag}/{len(df)} ({has_any_tag/len(df)*100:.1f}%)")

        num_tags = df[tag_columns].sum(axis=1)
        for n in range(1, int(num_tags.max()) + 1):
            count = (num_tags == n).sum()
            if count > 0:
                print(f"    Con {n} tag(s): {count:3} ({count/len(df)*100:.1f}%)")
    else:
        print(f"  Nessuna colonna tag trovata")
    print()

    print(f"Salvataggio: {output_path}")
    df.to_csv(output_path, index=False)
    print(f"Salvato\n")

    return df

def normalize_jd_dataset(input_path: Path, output_path: Path, ontology: SkillOntology) -> pd.DataFrame:
    """
    Normalizza il dataset JD.
    
    Campi normalizzati:
    - company_name → company_name_normalized (pulizia) [NUOVO v3]
    - requirements → requirements_normalized (mappatura ontologia)
    - nice_to_have → nice_to_have_normalized (mappatura ontologia)
    - constraints_seniority → constraints_seniority_normalized (standard)
    - min_experience_years → min_experience_years_normalized (validazione)
    - constraints_languages → constraints_languages_normalized (formato CEFR)
    - salary_* → salary_normalized (formato leggibile)
    """
    print(f"\n{'='*80}")
    print(f"NORMALIZZAZIONE DATASET JD")
    print(f"{'='*80}\n")

    print(f"Caricamento: {input_path}")
    df = pd.read_csv(input_path)
    print(f"Righe caricate: {len(df)}\n")

    # =========================================================================
    # NUOVO v3: Gestione company_name
    # =========================================================================
    print("Gestione company_name...")
    
    if 'company_name' in df.columns:
        # Normalizza (principalmente pulizia whitespace)
        df['company_name_normalized'] = df['company_name'].apply(normalize_company_name)
        
        # Statistiche sulle aziende
        valid_companies = df[df['company_name_normalized'] != '']
        unique_companies = valid_companies['company_name_normalized'].nunique()
        
        print(f"  Colonna trovata: ✓")
        print(f"  JD con company_name: {len(valid_companies)}/{len(df)}")
        print(f"  Aziende uniche: {unique_companies}")
        
        # Mostra distribuzione se ci sono più aziende
        if unique_companies > 0:
            print(f"\n  Distribuzione JD per azienda:")
            company_counts = df['company_name_normalized'].value_counts()
            for company, count in company_counts.head(10).items():
                if company:  # Salta valori vuoti
                    print(f"    {company:40} {count:3} JD")
            if len(company_counts) > 10:
                print(f"    ... e altre {len(company_counts) - 10} aziende")
    else:
        # Colonna non presente: crea colonna vuota per retrocompatibilità
        print(f"  ⚠ Colonna 'company_name' non trovata nel dataset")
        print(f"    → Creazione colonna vuota per retrocompatibilità...")
        df['company_name'] = ''
        df['company_name_normalized'] = ''
    
    print()
    # =========================================================================

    print("Normalizzazione requirements...")
    df['requirements_normalized'] = df['requirements'].apply(
        lambda x: normalize_skills_string(x, ontology)
    )
    print(f"  Prima: {df['requirements'].iloc[0][:80]}...")
    print(f"  Dopo:  {df['requirements_normalized'].iloc[0][:80]}...\n")

    print("Normalizzazione nice_to_have...")
    df['nice_to_have_normalized'] = df['nice_to_have'].apply(
        lambda x: normalize_skills_string(x, ontology)
    )
    print(f"  Prima: {df['nice_to_have'].iloc[0][:80]}...")
    print(f"  Dopo:  {df['nice_to_have_normalized'].iloc[0][:80]}...\n")

    print("Normalizzazione seniority...")
    df['constraints_seniority_normalized'] = df['constraints_seniority'].apply(
        lambda x: ontology.normalize_seniority(x)
    )
    for level, count in df['constraints_seniority_normalized'].value_counts().items():
        print(f"    {level:8} {count:3}")
    print()

    # =========================================================================
    # Normalizzazione min_experience_years (v2)
    # =========================================================================
    print("Normalizzazione min_experience_years...")
    
    if 'min_experience_years' in df.columns:
        # Normalizza usando la seniority per inferire valori mancanti
        df['min_experience_years_normalized'] = df.apply(
            lambda row: normalize_min_experience_years(
                row.get('min_experience_years'),
                row.get('constraints_seniority_normalized')
            ),
            axis=1
        )
        
        # Statistiche
        original_valid = df['min_experience_years'].notna().sum()
        print(f"  Valori originali presenti: {original_valid}/{len(df)}")
        
        # Distribuzione
        print(f"  Distribuzione anni richiesti:")
        for years, count in sorted(df['min_experience_years_normalized'].value_counts().items()):
            print(f"    {years} anni: {count:3} JD ({count/len(df)*100:.1f}%)")
        
        # Verifica coerenza seniority <-> anni
        print(f"\n  Verifica coerenza seniority ↔ anni:")
        warnings = []
        for idx, row in df.iterrows():
            seniority = row.get('constraints_seniority_normalized', '')
            min_years = row.get('min_experience_years_normalized', 0)
            is_consistent, warning = validate_seniority_experience_consistency(seniority, min_years)
            if not is_consistent:
                warnings.append((row.get('title', 'N/A'), warning))
        
        if warnings:
            print(f"    ⚠ Trovate {len(warnings)} incongruenze:")
            for title, warning in warnings[:5]:
                print(f"      - {title}: {warning}")
            if len(warnings) > 5:
                print(f"      ... e altre {len(warnings) - 5}")
        else:
            print(f"    ✓ Tutti i valori sono coerenti")
    else:
        # Colonna non presente: creala inferendo da seniority
        print(f"  ⚠ Colonna 'min_experience_years' non trovata nel dataset")
        print(f"    → Creazione colonna inferita da seniority...")
        
        df['min_experience_years_normalized'] = df['constraints_seniority_normalized'].apply(
            lambda x: SENIORITY_TO_YEARS.get(x, MIN_EXP_YEARS_DEFAULT)
        )
        
        print(f"  Distribuzione anni (inferiti):")
        for years, count in sorted(df['min_experience_years_normalized'].value_counts().items()):
            print(f"    {years} anni: {count:3} JD ({count/len(df)*100:.1f}%)")
    
    print()
    # =========================================================================

    print("Normalizzazione lingue...")
    df['constraints_languages_normalized'] = df['constraints_languages'].apply(
        lambda x: normalize_languages_string(x, ontology)
    )
    print(f"  Prima: {df['constraints_languages'].iloc[0]}")
    print(f"  Dopo:  {df['constraints_languages_normalized'].iloc[0]}\n")

    print("Normalizzazione salary...")

    def rebuild_salary_string(row):
        """Ricostruisce la stringa salary dai campi separati."""
        sal_min = row.get('salary_min')
        sal_max = row.get('salary_max')
        sal_curr = row.get('salary_currency')

        if pd.isna(sal_min) and pd.isna(sal_max):
            return ""

        if not pd.isna(sal_min) and not pd.isna(sal_max):
            temp = f"{int(sal_min)}-{int(sal_max)}"
        elif not pd.isna(sal_min):
            temp = f"{int(sal_min)}"
        else:
            temp = f"{int(sal_max)}"

        if sal_curr and not pd.isna(sal_curr):
            temp += f" {sal_curr}"

        return temp

    df['_temp_salary'] = df.apply(rebuild_salary_string, axis=1)
    df['salary_normalized'] = df['_temp_salary'].apply(extract_salary_range)
    df.drop(columns=['_temp_salary'], inplace=True)

    valid = df[df['salary_normalized'] != ""]
    print(f"  Normalizzati: {len(valid)}/{len(df)}")

    if len(valid) > 0:
        print(f"\n  Esempi:")
        for idx in valid.head(5).index:
            sal_min = df.loc[idx, 'salary_min']
            sal_max = df.loc[idx, 'salary_max']
            sal_curr = df.loc[idx, 'salary_currency']
            norm = df.loc[idx, 'salary_normalized']
            print(f"    {sal_min}-{sal_max} {sal_curr:3} → {norm}")
    print()

    print(f"Salvataggio: {output_path}")
    df.to_csv(output_path, index=False)
    print(f"Salvato\n")

    return df

# ============================================================================
# MAIN
# ============================================================================

def main():
    print("\n" + "="*80)
    print("SCRIPT DI NORMALIZZAZIONE DATASET CV ↔ JD")
    print("="*80 + "\n")

    if not ONTOLOGY_FILE.exists():
        print(f"ERRORE: File ontologia non trovato: {ONTOLOGY_FILE}")
        return

    if not INPUT_CV.exists():
        print(f"ERRORE: CV dataset non trovato: {INPUT_CV}")
        return

    if not INPUT_JD.exists():
        print(f"ERRORE: JD dataset non trovato: {INPUT_JD}")
        return

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    ontology = SkillOntology(ONTOLOGY_FILE)

    cv_df = normalize_cv_dataset(INPUT_CV, OUTPUT_CV, ontology)
    jd_df = normalize_jd_dataset(INPUT_JD, OUTPUT_JD, ontology)

    ontology.save_updated_ontology()

    print("\n" + "="*80)
    print("REPORT FINALE")
    print("="*80)

    print(f"\nCV normalizzati: {len(cv_df)}")
    print(f"JD normalizzate: {len(jd_df)}")
    print(f"Skill mappate: {len(ontology.skill_mappings)}")

    total_unmapped = len(ontology.data.get('unmapped_skills', {}).get('skills', []))
    if total_unmapped > 0:
        print(f"Skill da mappare: {total_unmapped}")
    else:
        print(f"Tutte le skill sono mappate")
    
    # NUOVO v3: Report aziende
    if 'company_name_normalized' in jd_df.columns:
        unique_companies = jd_df['company_name_normalized'].replace('', pd.NA).dropna().nunique()
        print(f"Aziende uniche: {unique_companies}")

    print(f"\nOUTPUT:")
    print(f"  {OUTPUT_CV}")
    print(f"  {OUTPUT_JD}")
    print(f"  {ONTOLOGY_FILE} (aggiornato)")

    print("="*80 + "\n")

if __name__ == "__main__":
    main()
  
