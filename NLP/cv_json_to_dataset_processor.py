"""
cv_json_to_csv_processor.py
Converte JSON CV in dataset CSV con gestione duplicati e tag dinamici
"""

import json
from pathlib import Path
from typing import Dict, Set, Tuple
from datetime import datetime
import pandas as pd

INPUT_FOLDER = "data/cvs"
OUTPUT_FOLDER = "Dataset"
OUTPUT_FILENAME = "cv_dataset.csv"

ARRAY_SEP = " | "
LIST_SEP = ", "


def discover_all_tags(input_path: Path) -> Set[str]:
    all_tags = set()
    for json_file in input_path.glob("*.json"):
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            tags_section = data.get('Tags') or data.get('tags') or {}
            if isinstance(tags_section, dict):
                all_tags.update(tags_section.keys())
        except:
            continue
    return all_tags


def get_existing_identifiers(output_path: Path) -> Tuple[Set[str], Dict[str, int]]:
    if not output_path.exists():
        return set(), {}
    try:
        df = pd.read_csv(output_path, encoding='utf-8')
        existing_sha256 = set(df['file_sha256'].dropna().astype(str)) if 'file_sha256' in df.columns else set()
        existing_sha256.discard('')
        user_id_to_index = {}
        if 'user_id' in df.columns:
            for idx, user_id in enumerate(df['user_id']):
                if pd.notna(user_id) and str(user_id).strip():
                    user_id_to_index[str(user_id)] = idx
        return existing_sha256, user_id_to_index
    except Exception:
        return set(), {}


def extract_identifiers_from_json(json_path: Path) -> Tuple[str, str]:
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
        user_id = str(data.get('user_id', '')) if data.get('user_id') else ''
        sha256 = str(data.get('file_sha256', '')) if data.get('file_sha256') else ''
        return user_id, sha256
    except Exception:
        return '', ''


def flatten_personal_info(data: Dict) -> Dict:
    if not data:
        data = {}
    return {
        'pi_full_name': data.get('full_name') or '',
        'pi_email': data.get('email') or '',
        'pi_phone': data.get('phone') or '',
        'pi_address': data.get('address') or '',
        'pi_city': data.get('city') or '',
        'pi_country': data.get('country') or '',
        'pi_postal_code': data.get('postal_code') or '',
        'pi_linkedin': data.get('linkedin') or '',
        'pi_github': data.get('github') or '',
        'pi_website': data.get('website') or ''
    }


def flatten_tags(data: Dict, all_known_tags: Set[str]) -> Dict:
    if not data:
        data = {}
    tags_section = data.get('Tags') or data.get('tags') or {}
    result = {}
    for tag_name in all_known_tags:
        col_name = f"tag_{tag_name}"
        tag_value = tags_section.get(tag_name)
        result[col_name] = True if tag_value is True else None
    return result


def concatenate_experience(items: list) -> str:
    if not items:
        return ""
    result = []
    for exp in items:
        title = exp.get('title') or 'N/A'
        company = exp.get('company') or 'N/A'
        city = exp.get('city') or ''
        start = exp.get('start_date') or ''
        end = 'Present' if exp.get('is_current') else (exp.get('end_date') or '')
        location = f" ({city})" if city else ""
        period = f" [{start} - {end}]" if start else ""
        result.append(f"{title} @ {company}{location}{period}")
    return ARRAY_SEP.join(result)


def concatenate_education(items: list) -> str:
    if not items:
        return ""
    result = []
    for edu in items:
        degree = edu.get('degree') or 'N/A'
        field = edu.get('field_of_study') or ''
        institution = edu.get('institution') or 'N/A'
        year = edu.get('graduation_year') or ''
        field_str = f" in {field}" if field else ""
        year_str = f" ({year})" if year else ""
        result.append(f"{degree}{field_str} @ {institution}{year_str}")
    return ARRAY_SEP.join(result)


def concatenate_skills(items: list) -> str:
    if not items:
        return ""
    result = []
    for skill in items:
        name = skill.get('name') or 'N/A'
        category = skill.get('category') or ''
        proficiency = skill.get('proficiency') or ''
        details = [x for x in [category, proficiency] if x]
        detail_str = f" ({LIST_SEP.join(details)})" if details else ""
        result.append(f"{name}{detail_str}")
    return LIST_SEP.join(result)


def concatenate_languages(items: list) -> str:
    if not items:
        return ""
    result = []
    for lang in items:
        name = lang.get('name') or 'N/A'
        level = lang.get('level') or lang.get('proficiency') or ''
        cert = lang.get('certificate') or ''
        cert_year = lang.get('certificate_year') or ''
        details = []
        if level:
            details.append(level)
        if cert:
            details.append(f"{cert} {cert_year}" if cert_year else cert)
        detail_str = f" ({LIST_SEP.join(details)})" if details else ""
        result.append(f"{name}{detail_str}")
    return LIST_SEP.join(result)


def concatenate_certifications(items: list) -> str:
    if not items:
        return ""
    result = []
    for cert in items:
        name = cert.get('name') or 'N/A'
        issuer = cert.get('issuer') or ''
        date = cert.get('date_obtained') or ''
        details = [x for x in [issuer, date] if x]
        detail_str = f" ({LIST_SEP.join(details)})" if details else ""
        result.append(f"{name}{detail_str}")
    return ARRAY_SEP.join(result)


def concatenate_projects(items: list) -> str:
    if not items:
        return ""
    result = []
    for proj in items:
        name = proj.get('name') or 'N/A'
        desc = proj.get('description') or ''
        tech = proj.get('technologies') or []
        desc_str = f": {desc}" if desc else ""
        tech_str = f" [{LIST_SEP.join(tech)}]" if tech else ""
        result.append(f"{name}{desc_str}{tech_str}")
    return ARRAY_SEP.join(result)


def flatten_preferences(data: Dict) -> Dict:
    if not data:
        return {
            'pref_desired_roles': "",
            'pref_preferred_locations': "",
            'pref_remote_preference': "",
            'pref_salary_expectation': "",
            'pref_availability': ""
        }
    return {
        'pref_desired_roles': LIST_SEP.join(data.get('desired_roles') or []),
        'pref_preferred_locations': LIST_SEP.join(data.get('preferred_locations') or []),
        'pref_remote_preference': data.get('remote_preference') or '',
        'pref_salary_expectation': data.get('salary_expectation') or '',
        'pref_availability': data.get('availability') or ''
    }


def json_to_row(data: Dict, source_file: str, all_known_tags: Set[str]) -> Dict:
    row = {
        'user_id': data.get('user_id') or '',
        'source_file': source_file,
        'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'document_id': data.get('document_id') or '',
        'document_type': data.get('document_type') or '',
        'file_sha256': data.get('file_sha256') or '',
        'summary': data.get('summary') or ''
    }
    row.update(flatten_personal_info(data.get('personal_info') or {}))
    row['experience'] = concatenate_experience(data.get('experience') or [])
    row['education'] = concatenate_education(data.get('education') or [])
    row['skills'] = concatenate_skills(data.get('skills') or [])
    row['languages'] = concatenate_languages(data.get('languages') or [])
    row['certifications'] = concatenate_certifications(data.get('certifications') or [])
    row['projects'] = concatenate_projects(data.get('projects') or [])
    row.update(flatten_preferences(data.get('preferences')))
    row.update(flatten_tags(data, all_known_tags))
    return row


def process_files(input_dir: str, output_dir: str, output_file: str):
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    full_output_path = output_path / output_file
    processed_folder = input_path.parent / "cvs_processed"
    processed_folder.mkdir(exist_ok=True)

    if not input_path.exists():
        print(f"Errore: cartella {input_dir} non trovata")
        return False

    json_files = list(input_path.glob("*.json"))
    if not json_files:
        print(f"Nessun file JSON in {input_dir}")
        return False

    all_known_tags = discover_all_tags(input_path)
    existing_sha256, user_id_to_index = get_existing_identifiers(full_output_path)

    files_to_add = []
    files_to_update = []

    for json_file in json_files:
        user_id, sha256 = extract_identifiers_from_json(json_file)

        if sha256 and sha256 in existing_sha256:
            json_file.rename(processed_folder / json_file.name)
        elif user_id and user_id in user_id_to_index:
            if sha256 and sha256 not in existing_sha256:
                files_to_update.append((json_file, user_id, sha256, user_id_to_index[user_id]))
            json_file.rename(processed_folder / json_file.name)
        else:
            files_to_add.append(json_file)

    if not files_to_add and not files_to_update:
        print("Nessun file da processare")
        return True

    rows_to_add = []
    rows_to_update = []
    errors = []

    for json_file in files_to_add:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            rows_to_add.append(json_to_row(data, json_file.name, all_known_tags))
            json_file.rename(processed_folder / json_file.name)
        except Exception as e:
            errors.append((json_file.name, str(e)))

    for json_file, user_id, sha256, row_index in files_to_update:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            rows_to_update.append((row_index, json_to_row(data, json_file.name, all_known_tags)))
            json_file.rename(processed_folder / json_file.name)
        except Exception as e:
            errors.append((json_file.name, str(e)))

    output_path.mkdir(parents=True, exist_ok=True)

    if full_output_path.exists():
        existing_df = pd.read_csv(full_output_path, encoding='utf-8')
        for row_index, row_data in rows_to_update:
            for col, value in row_data.items():
                if col not in existing_df.columns:
                    existing_df[col] = None
                existing_df.at[row_index, col] = value
        if rows_to_add:
            new_df = pd.DataFrame(rows_to_add)
            final_df = pd.concat([existing_df, new_df], ignore_index=True)
        else:
            final_df = existing_df
    else:
        if rows_to_add:
            final_df = pd.DataFrame(rows_to_add)
        else:
            print("Nessuna riga da salvare")
            return False

    base_cols = [
        'user_id', 'source_file', 'processed_at', 'document_id', 'document_type', 'file_sha256',
        'pi_full_name', 'pi_email', 'pi_phone', 'pi_address', 'pi_city', 'pi_country',
        'pi_postal_code', 'pi_linkedin', 'pi_github', 'pi_website', 'summary',
        'experience', 'education', 'skills', 'languages', 'certifications', 'projects',
        'pref_desired_roles', 'pref_preferred_locations', 'pref_remote_preference',
        'pref_salary_expectation', 'pref_availability'
    ]
    tag_cols = sorted([f"tag_{tag}" for tag in all_known_tags])
    cols = base_cols + tag_cols
    existing_cols = [c for c in cols if c in final_df.columns]
    final_df = final_df[existing_cols]
    final_df.to_csv(full_output_path, index=False, encoding='utf-8')

    print(f"Completato: {len(rows_to_add)} nuovi, {len(rows_to_update)} aggiornati, {len(errors)} errori")
    if errors:
        for fname, error in errors:
            print(f"  ERR: {fname} - {error}")

    return True


if __name__ == "__main__":
    process_files(INPUT_FOLDER, OUTPUT_FOLDER, OUTPUT_FILENAME)
