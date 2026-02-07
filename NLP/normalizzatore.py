# -*- coding: utf-8 -*-
"""
Script di Normalizzazione Dataset CV e JD
Calcola seniority da anni di esperienza reali invece che da keyword nei titoli.
Normalizza salary in formato leggibile e gestisce tag DE&I.
"""

import json
import pandas as pd
import re
from pathlib import Path
from typing import Dict, List, Set, Tuple, Optional
from datetime import datetime
from dateutil import parser
from collections import defaultdict
import logging

# Basic console logging (file handler configured after OUTPUT_DIR is known)
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# ============================================================================
# CONFIGURAZIONE
# ============================================================================

# I dataset CSV (cv_dataset.csv, jd_dataset.csv) sono creati in "Dataset"
# relativa alla working directory del backend (/app).
DATASET_DIR = Path("Dataset")
INPUT_CV = DATASET_DIR / "cv_dataset.csv"
INPUT_JD = DATASET_DIR / "jd_dataset.csv"

# L'ontologia invece vive nella cartella NLP, accanto a questo script,
# in "NLP/Dataset/skill_ontology.json" (montata come ./NLP nel container).
if '__file__' in globals():
    BASE_DIR = Path(__file__).parent
else:
    BASE_DIR = Path.cwd()

ONTOLOGY_FILE = BASE_DIR / "Dataset" / "skill_ontology.json"

OUTPUT_DIR = DATASET_DIR / "normalized"
OUTPUT_CV = OUTPUT_DIR / "cv_dataset_normalized.csv"
OUTPUT_JD = OUTPUT_DIR / "jd_dataset_normalized.csv"

# Configure file logging now that OUTPUT_DIR is defined
try:
    LOG_DIR = OUTPUT_DIR / "logs"
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    LOG_FILE = LOG_DIR / "normalizzatore.log"
    # add file handler while keeping existing stream handlers
    fh = logging.FileHandler(str(LOG_FILE))
    fh.setLevel(logging.INFO)
    formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
    fh.setFormatter(formatter)
    logger.addHandler(fh)
    logger.info(f"Logging initialized. Log file: {LOG_FILE}")
except Exception:
    logger.exception("Impossibile inizializzare il file di log")

# ============================================================================
# CARICAMENTO ONTOLOGIA
# ============================================================================

class SkillOntology:

    def __init__(self, ontology_path: Path):
        logger.info(f"Caricamento ontologia da: {ontology_path}")
        self.ontology_path = ontology_path

        with open(ontology_path, 'r', encoding='utf-8') as f:
            self.data = json.load(f)

        self.skill_mappings = self.data.get('skill_mappings', {})
        self.seniority_mappings = self.data.get('seniority_mappings', {})
        self.cefr_mappings = self.data.get('cefr_mappings', {})
        self.metadata = self.data.get('_metadata', {})

        # Rimuovi commenti
        self.skill_mappings = {k: v for k, v in self.skill_mappings.items()
                               if not k.startswith('_')}
        self.seniority_mappings = {k: v for k, v in self.seniority_mappings.items()
                                   if not k.startswith('_')}
        self.cefr_mappings = {k: v for k, v in self.cefr_mappings.items()
                              if not k.startswith('_')}

        self.unmapped_skills = defaultdict(int)
        previous_unmapped = self.data.get('unmapped_skills', {}).get('skills', [])
        self.previous_unmapped = {item['skill'] for item in previous_unmapped}

        logger.info(f"  Mappature skill: {len(self.skill_mappings)}")
        logger.info(f"  Mappature seniority: {len(self.seniority_mappings)}")
        logger.info(f"  Mappature CEFR: {len(self.cefr_mappings)}")
        if self.previous_unmapped:
            logger.info(f"  Skill da mappare: {len(self.previous_unmapped)}")
        logger.debug("")

    def normalize_skill(self, skill: str) -> str:
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
        if not level_str or pd.isna(level_str):
            return "B2"

        level_lower = level_str.lower().strip()

        if level_lower in self.cefr_mappings:
            return self.cefr_mappings[level_lower]

        return "B2"

    def _years_to_seniority(self, years: float) -> str:
        if years < 2.0:
            return "junior"
        elif years < 5.0:
            return "mid"
        else:
            return "senior"

    def save_updated_ontology(self):
        logger.info("Aggiornamento ontologia...")

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

        logger.info(f"  Aggiornata: {self.ontology_path}")
        logger.info(f"  Skill non mappate: {len(existing_unmapped)}")

        if len(new_unmapped) > 0:
            logger.info(f"  Nuove skill: {len(new_unmapped)}")
            logger.info("  Top 10 skill da mappare:")
            for item in new_unmapped[:10]:
                logger.info(f"    {item['skill']:35} (freq: {item['frequency']:3})")

        if len(existing_unmapped) > 0:
            logger.info(f"  Azione richiesta: rivedi unmapped_skills in {self.ontology_path}")
        else:
            logger.info(f"  Tutte le skill sono mappate")

        logger.debug("")

# ============================================================================
# PARSING DATE
# ============================================================================

def parse_date_flexible(date_str: str) -> Optional[datetime]:
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
    if not salary_str or pd.isna(salary_str):
        return ""

    salary_clean = str(salary_str).strip()

    words_to_remove = ['circa', 'about', 'around', 'approximately']
    for word in words_to_remove:
        salary_clean = re.sub(rf'\b{word}\b', '', salary_clean, flags=re.IGNORECASE)

    salary_clean = re.sub(r'\s+', ' ', salary_clean).strip()

    return salary_clean

# ============================================================================
# NORMALIZZAZIONE DATASET
# ============================================================================

def normalize_cv_dataset(input_path: Path, output_path: Path, ontology: SkillOntology) -> pd.DataFrame:
    logger.info("%s", "="*80)
    logger.info("NORMALIZZAZIONE DATASET CV")
    logger.info("%s\n", "="*80)

    logger.info(f"Caricamento: {input_path}")
    df = pd.read_csv(input_path)
    logger.info(f"Righe caricate: {len(df)}")

    # Sanitizza le colonne testuali per evitare errori di tipo (es. float/NaN)
    # che causano TypeError quando si applicano slice tipo [:80].
    for col in [
        'requirements',
        'nice_to_have',
        'constraints_languages',
        'constraints_seniority',
    ]:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    if len(df) == 0:
        logger.info("CV dataset vuoto: nessuna normalizzazione necessaria.")
        logger.info(f"Salvataggio: {output_path}")
        df.to_csv(output_path, index=False)
        logger.info("Salvato")
        return df

    logger.info("Normalizzazione skills...")
    df['skills_normalized'] = df['skills'].apply(
        lambda x: normalize_skills_string(x, ontology)
    )
    logger.debug(f"  Prima:  {df['skills'].iloc[0][:80]}...")
    logger.debug(f"  Dopo:   {df['skills_normalized'].iloc[0][:80]}...")

    logger.info("Normalizzazione lingue...")
    df['languages_normalized'] = df['languages'].apply(
        lambda x: normalize_languages_string(x, ontology)
    )
    logger.debug(f"  Prima: {df['languages'].iloc[0]}")
    logger.debug(f"  Dopo:  {df['languages_normalized'].iloc[0]}")

    logger.info("Calcolo seniority da anni di esperienza...")
    seniority_data = df['experience'].apply(infer_seniority_from_experience)
    df['inferred_seniority'] = seniority_data.apply(lambda x: x[0])
    df['years_of_experience'] = seniority_data.apply(lambda x: x[1])

    logger.info("  Distribuzione seniority:")
    for level, count in df['inferred_seniority'].value_counts().items():
        avg_years = df[df['inferred_seniority'] == level]['years_of_experience'].mean()
        logger.info(f"    {level:8} {count:3} ({count/len(df)*100:5.1f}%)  →  media {avg_years:.1f} anni")

    logger.info("  Statistiche esperienza:")
    logger.info(f"    Min:    {df['years_of_experience'].min():.1f} anni")
    logger.info(f"    Media:  {df['years_of_experience'].mean():.1f} anni")
    logger.info(f"    Max:    {df['years_of_experience'].max():.1f} anni")
    logger.debug("")

    logger.info("Normalizzazione salary...")
    df['pref_salary_normalized'] = df['pref_salary_expectation'].apply(extract_salary_range)

    valid = df[df['pref_salary_normalized'] != ""]
    logger.info(f"  Normalizzati: {len(valid)}/{len(df)}")

    if len(valid) > 0:
        logger.info("  Esempi:")
        for idx in valid.head(5).index:
            orig = df.loc[idx, 'pref_salary_expectation']
            norm = df.loc[idx, 'pref_salary_normalized']
            logger.info(f"    {orig:30} → {norm}")
    logger.debug("")

    logger.info("Normalizzazione tags...")

    tag_columns = [col for col in df.columns if col.startswith('tag_')]

    if tag_columns:
        logger.info(f"  Trovate {len(tag_columns)} colonne tag:")

        for tag_col in tag_columns:
            tag_name = tag_col.replace('tag_', '')
            df[tag_col] = df[tag_col].apply(lambda x: True if x is True else None)
            after_true = (df[tag_col] == True).sum()
            print(f"    {tag_name:25} {after_true:3} True, {len(df) - after_true:3} None")

        logger.info(f"  Distribuzione candidati:")
        has_any_tag = df[tag_columns].any(axis=1).sum()
        logger.info(f"    Con almeno 1 tag: {has_any_tag}/{len(df)} ({has_any_tag/len(df)*100:.1f}%)")

        num_tags = df[tag_columns].sum(axis=1)
        for n in range(1, int(num_tags.max()) + 1):
            count = (num_tags == n).sum()
            if count > 0:
                print(f"    Con {n} tag(s): {count:3} ({count/len(df)*100:.1f}%)")
    else:
        logger.info("  Nessuna colonna tag trovata")
    logger.debug("")

    logger.info(f"Salvataggio: {output_path}")
    df.to_csv(output_path, index=False)
    logger.info("Salvato")

    return df

def normalize_jd_dataset(input_path: Path, output_path: Path, ontology: SkillOntology) -> pd.DataFrame:
    logger.info("%s", "="*80)
    logger.info("NORMALIZZAZIONE DATASET JD")
    logger.info("%s\n", "="*80)

    logger.info(f"Caricamento: {input_path}")
    df = pd.read_csv(input_path)
    logger.info(f"Righe caricate: {len(df)}")

    if len(df) == 0:
        logger.info("JD dataset vuoto: nessuna normalizzazione necessaria.")
        logger.info(f"Salvataggio: {output_path}")
        df.to_csv(output_path, index=False)
        logger.info("Salvato")
        return df

    logger.info("Normalizzazione requirements...")
    df['requirements_normalized'] = df['requirements'].apply(
        lambda x: normalize_skills_string(x, ontology)
    )
    if len(df) > 0:
        req_before = str(df['requirements'].iloc[0])
        req_after = str(df['requirements_normalized'].iloc[0])
        print(f"  Prima: {req_before[:80]}...")
        print(f"  Dopo:  {req_after[:80]}...\n")

    logger.info("Normalizzazione nice_to_have...")
    df['nice_to_have_normalized'] = df['nice_to_have'].apply(
        lambda x: normalize_skills_string(x, ontology)
    )
    if len(df) > 0:
        nth_before = str(df['nice_to_have'].iloc[0])
        nth_after = str(df['nice_to_have_normalized'].iloc[0])
        print(f"  Prima: {nth_before[:80]}...")
        print(f"  Dopo:  {nth_after[:80]}...\n")

    logger.info("Normalizzazione seniority...")
    df['constraints_seniority_normalized'] = df['constraints_seniority'].apply(
        lambda x: ontology.normalize_seniority(x)
    )
    for level, count in df['constraints_seniority_normalized'].value_counts().items():
        print(f"    {level:8} {count:3}")
    print()

    logger.info("Normalizzazione lingue...")
    df['constraints_languages_normalized'] = df['constraints_languages'].apply(
        lambda x: normalize_languages_string(x, ontology)
    )
    logger.debug(f"  Prima: {df['constraints_languages'].iloc[0]}")
    logger.debug(f"  Dopo:  {df['constraints_languages_normalized'].iloc[0]}")

    logger.info("Normalizzazione salary...")

    def rebuild_salary_string(row):
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
    logger.info(f"  Normalizzati: {len(valid)}/{len(df)}")

    if len(valid) > 0:
        print(f"\n  Esempi:")
        for idx in valid.head(5).index:
            sal_min = df.loc[idx, 'salary_min']
            sal_max = df.loc[idx, 'salary_max']
            sal_curr = df.loc[idx, 'salary_currency']
            norm = df.loc[idx, 'salary_normalized']
            print(f"    {sal_min}-{sal_max} {sal_curr:3} → {norm}")
    print()

    logger.info(f"Salvataggio: {output_path}")
    df.to_csv(output_path, index=False)
    logger.info("Salvato")

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

    logger.info("%s", "="*80)
    logger.info("REPORT FINALE")
    logger.info("%s", "="*80)

    logger.info(f"CV normalizzati: {len(cv_df)}")
    logger.info(f"JD normalizzate: {len(jd_df)}")
    logger.info(f"Skill mappate: {len(ontology.skill_mappings)}")

    total_unmapped = len(ontology.data.get('unmapped_skills', {}).get('skills', []))
    if total_unmapped > 0:
        logger.info(f"Skill da mappare: {total_unmapped}")
    else:
        logger.info(f"Tutte le skill sono mappate")

    logger.info("OUTPUT:")
    logger.info(f"  {OUTPUT_CV}")
    logger.info(f"  {OUTPUT_JD}")
    logger.info(f"  {ONTOLOGY_FILE} (aggiornato)")

    logger.info("%s", "="*80)

if __name__ == "__main__":
    main()

