"""
json_to_csv_processor.py
Converte file JSON CV in un dataset CSV tabulare
Con controllo duplicati e pulizia utenti eliminati
MODIFICATO: aggiunto supporto per tag dinamici
"""

import json
import os
from pathlib import Path
from typing import List, Dict, Set, Tuple
from datetime import datetime
import pandas as pd


INPUT_FOLDER = "/var/lib/docker/piazzati-data/cvs"
OUTPUT_FOLDER = "Dataset"
OUTPUT_FILENAME = "cv_dataset.csv"

ARRAY_SEP = " | "
LIST_SEP = ", "


def get_active_user_ids(input_path: Path) -> Set[str]:
    """
    Estrae tutti gli user_id dai file JSON presenti nella cartella.
    Rappresenta gli utenti attivi nel sistema.
    """
    active_users = set()

    json_files = list(input_path.glob("*.json"))

    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            user_id = str(data.get('user_id', '')) if data.get('user_id') else ''
            if user_id:
                active_users.add(user_id)
        except:
            continue

    return active_users


def discover_all_tags(input_path: Path) -> Set[str]:
    """
    Scansiona tutti i JSON nella cartella e raccoglie tutti i tag univoci.
    Questo permette di creare colonne dinamiche per tag presenti e futuri.
    
    Perché serve:
    - I tag cambiano nel tempo (nuovi tag possono essere aggiunti)
    - Dobbiamo creare una colonna CSV per ogni tag esistente
    - Evita hardcoding dei nomi dei tag
    
    Returns:
        Set di stringhe con i nomi di tutti i tag trovati 
        (es: {'women_in_tech', '1_2_generation', 'refugee_background'})
    """
    all_tags = set()
    
    json_files = list(input_path.glob("*.json"))
    
    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
            
            # Estrae tutti i tag dalla sezione "Tags" (case-insensitive)
            tags_section = data.get('Tags') or data.get('tags') or {}
            
            if isinstance(tags_section, dict):
                all_tags.update(tags_section.keys())
        except:
            continue
    
    return all_tags


def clean_deleted_users(output_path: Path, active_user_ids: Set[str]) -> int:
    """
    Rimuove dal dataset gli utenti che non hanno più file JSON.
    Restituisce il numero di righe eliminate.
    """
    if not output_path.exists():
        return 0

    try:
        df = pd.read_csv(output_path, encoding='utf-8')

        if 'user_id' not in df.columns:
            print("  Colonna user_id non trovata nel dataset")
            return 0

        original_count = len(df)

        deleted_users = []
        for idx, user_id in enumerate(df['user_id']):
            if pd.notna(user_id) and str(user_id).strip():
                if str(user_id) not in active_user_ids:
                    deleted_users.append(str(user_id))

        if deleted_users:
            df = df[df['user_id'].isin(active_user_ids) | df['user_id'].isna()]
            df.to_csv(output_path, index=False, encoding='utf-8')

            removed_count = original_count - len(df)

            print(f"  Utenti rimossi: {len(set(deleted_users))}")
            print(f"  Righe eliminate: {removed_count}")

            if len(deleted_users) <= 10:
                for user_id in set(deleted_users):
                    print(f"    - {user_id}")

            return removed_count
        else:
            print("  Nessun utente da rimuovere")
            return 0

    except Exception as e:
        print(f"  Errore durante la pulizia: {e}")
        return 0


def get_existing_identifiers(output_path: Path) -> Tuple[Set[str], Dict[str, int]]:
    if not output_path.exists():
        return set(), {}

    try:
        df = pd.read_csv(output_path, encoding='utf-8')

        existing_sha256 = set()
        if 'file_sha256' in df.columns:
            existing_sha256 = set(df['file_sha256'].dropna().astype(str))
            existing_sha256.discard('')

        user_id_to_index = {}
        if 'user_id' in df.columns:
            for idx, user_id in enumerate(df['user_id']):
                if pd.notna(user_id) and str(user_id).strip():
                    user_id_to_index[str(user_id)] = idx

        return existing_sha256, user_id_to_index

    except Exception as e:
        print(f"Avviso: impossibile leggere il CSV esistente: {e}")
        return set(), {}


def extract_identifiers_from_json(json_path: Path) -> Tuple[str, str]:
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        user_id = str(data.get('user_id', '')) if data.get('user_id') else ''
        sha256 = str(data.get('file_sha256', '')) if data.get('file_sha256') else ''

        return user_id, sha256

    except Exception as e:
        print(f"  Errore lettura da {json_path.name}: {e}")
        return '', ''


def flatten_personal_info(data: Dict) -> Dict:
    if not data:
        data = {}

    return {
        'pi_full_name': data.get('full_name', ''),
        'pi_email': data.get('email', ''),
        'pi_phone': data.get('phone', ''),
        'pi_address': data.get('address', ''),
        'pi_city': data.get('city', ''),
        'pi_country': data.get('country', ''),
        'pi_postal_code': data.get('postal_code', ''),
        'pi_linkedin': data.get('linkedin', ''),
        'pi_github': data.get('github', ''),
        'pi_website': data.get('website', '')
    }


def flatten_tags(data: Dict, all_known_tags: Set[str]) -> Dict:
    """
    Estrae i tag dal JSON e crea un dizionario con una chiave per ogni tag conosciuto.
    
    Perché serve:
    - I tag indicano appartenenza a gruppi DE&I (women_in_tech, 1_2_generation, etc.)
    - Servono per analisi fairness e metriche di diversità (obiettivo NLP doc)
    - Ogni tag diventa una colonna booleana nel CSV
    
    Args:
        data: sezione "Tags" del JSON
        all_known_tags: set completo di tutti i tag da tutti i JSON
    
    Returns:
        Dizionario {tag_name: True/None} per ogni tag
        - True se il tag è presente e true nel JSON
        - None se il tag non esiste o è false/null
    
    Esempio:
        Input JSON: {"Tags": {"women_in_tech": true, "1_2_generation": true}}
        all_known_tags: {"women_in_tech", "1_2_generation", "refugee_background"}
        Output: {
            "tag_women_in_tech": True,
            "tag_1_2_generation": True,
            "tag_refugee_background": None
        }
    """
    if not data:
        data = {}
    
    # Estrae la sezione Tags (case-insensitive)
    tags_section = data.get('Tags') or data.get('tags') or {}
    
    result = {}
    
    # Per ogni tag conosciuto nel sistema
    for tag_name in all_known_tags:
        # Prefisso "tag_" per distinguere chiaramente le colonne tag
        col_name = f"tag_{tag_name}"
        
        # Valore: True se presente e true, altrimenti None (null nel CSV)
        tag_value = tags_section.get(tag_name)
        
        # Convertiamo in True/None per rispettare i requisiti
        if tag_value is True:
            result[col_name] = True
        else:
            result[col_name] = None
    
    return result


def concatenate_experience(items: List[Dict]) -> str:
    if not items:
        return ""

    result = []
    for exp in items:
        title = exp.get('title', 'N/A')
        company = exp.get('company', 'N/A')
        city = exp.get('city', '')
        start = exp.get('start_date', '')
        end = 'Present' if exp.get('is_current') else exp.get('end_date', '')

        location = f" ({city})" if city else ""
        period = f" [{start} - {end}]" if start else ""
        result.append(f"{title} @ {company}{location}{period}")

    return ARRAY_SEP.join(result)


def concatenate_education(items: List[Dict]) -> str:
    if not items:
        return ""

    result = []
    for edu in items:
        degree = edu.get('degree', 'N/A')
        field = edu.get('field_of_study', '')
        institution = edu.get('institution', 'N/A')
        year = edu.get('graduation_year', '')

        field_str = f" in {field}" if field else ""
        year_str = f" ({year})" if year else ""
        result.append(f"{degree}{field_str} @ {institution}{year_str}")

    return ARRAY_SEP.join(result)


def concatenate_skills(items: List[Dict]) -> str:
    if not items:
        return ""

    result = []
    for skill in items:
        name = skill.get('name', 'N/A')
        category = skill.get('category', '')
        proficiency = skill.get('proficiency', '')

        details = [x for x in [category, proficiency] if x]
        detail_str = f" ({LIST_SEP.join(details)})" if details else ""
        result.append(f"{name}{detail_str}")

    return LIST_SEP.join(result)


def concatenate_languages(items: List[Dict]) -> str:
    if not items:
        return ""

    result = []
    for lang in items:
        name = lang.get('name', 'N/A')
        level = lang.get('level') or lang.get('proficiency', '')
        cert = lang.get('certificate', '')
        cert_year = lang.get('certificate_year', '')

        details = []
        if level:
            details.append(level)
        if cert:
            details.append(f"{cert} {cert_year}" if cert_year else cert)

        detail_str = f" ({LIST_SEP.join(details)})" if details else ""
        result.append(f"{name}{detail_str}")

    return LIST_SEP.join(result)


def concatenate_certifications(items: List[Dict]) -> str:
    if not items:
        return ""

    result = []
    for cert in items:
        name = cert.get('name', 'N/A')
        issuer = cert.get('issuer', '')
        date = cert.get('date_obtained', '')

        details = [x for x in [issuer, date] if x]
        detail_str = f" ({LIST_SEP.join(details)})" if details else ""
        result.append(f"{name}{detail_str}")

    return ARRAY_SEP.join(result)


def concatenate_projects(items: List[Dict]) -> str:
    if not items:
        return ""

    result = []
    for proj in items:
        name = proj.get('name', 'N/A')
        desc = proj.get('description', '')
        tech = proj.get('technologies', [])

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
        'pref_desired_roles': LIST_SEP.join(data.get('desired_roles', [])),
        'pref_preferred_locations': LIST_SEP.join(data.get('preferred_locations', [])),
        'pref_remote_preference': data.get('remote_preference', ''),
        'pref_salary_expectation': data.get('salary_expectation', ''),
        'pref_availability': data.get('availability', '')
    }


def json_to_row(data: Dict, source_file: str, all_known_tags: Set[str]) -> Dict:
    """
    Converte un JSON completo in una riga CSV piatta.
    
    MODIFICATO: aggiunto parametro all_known_tags per gestire tag dinamici
    """
    row = {
        'user_id': data.get('user_id', ''),
        'source_file': source_file,
        'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'document_id': data.get('document_id', ''),
        'document_type': data.get('document_type', ''),
        'file_sha256': data.get('file_sha256', ''),
        'summary': data.get('summary', '')
    }

    row.update(flatten_personal_info(data.get('personal_info', {})))

    row['experience'] = concatenate_experience(data.get('experience', []))
    row['education'] = concatenate_education(data.get('education', []))
    row['skills'] = concatenate_skills(data.get('skills', []))
    row['languages'] = concatenate_languages(data.get('languages', []))
    row['certifications'] = concatenate_certifications(data.get('certifications', []))
    row['projects'] = concatenate_projects(data.get('projects', []))

    row.update(flatten_preferences(data.get('preferences')))
    
    # NOVITÀ: aggiungiamo i tag dinamici
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

    processed_folder = input_path.parent / "cvs_processed"
    processed_folder.mkdir(exist_ok=True)
    json_files = list(input_path.glob("*.json"))

    if not json_files:
        print(f"Nessun file JSON trovato in {input_dir}")
        return False

    print(f"Trovati {len(json_files)} file JSON")
    
    # NOVITÀ: scopriamo tutti i tag prima di processare
    print(f"\nDiscovery tag dinamici...")
    all_known_tags = discover_all_tags(input_path)
    
    if all_known_tags:
        print(f"  Tag trovati: {sorted(all_known_tags)}")
        print(f"  Verranno create {len(all_known_tags)} colonne tag")
    else:
        print(f"  Nessun tag trovato nei JSON")

    # print(f"\nControllo utenti eliminati...")
    # active_user_ids = get_active_user_ids(input_path)
    # print(f"  Utenti attivi nei JSON: {len(active_user_ids)}")
    # removed_count = clean_deleted_users(full_output_path, active_user_ids)

    print(f"\nControllo duplicati nel dataset esistente...")
    existing_sha256, user_id_to_index = get_existing_identifiers(full_output_path)

    if existing_sha256 or user_id_to_index:
        print(f"  SHA256 unici: {len(existing_sha256)}")
        print(f"  User ID unici: {len(user_id_to_index)}")
    else:
        print(f"  Nessun dataset esistente")

    print(f"\nAnalisi file JSON...")

    files_to_add = []
    files_to_update = []
    files_skipped_sha = []
    files_skipped_both = []
    files_no_identifiers = []

    for json_file in json_files:
        user_id, sha256 = extract_identifiers_from_json(json_file)

        if not user_id and not sha256:
            files_no_identifiers.append(json_file.name)
            files_to_add.append(json_file)

        elif sha256 and sha256 in existing_sha256:
            files_skipped_sha.append((json_file.name, user_id, sha256))
            print(f"  SKIP (SHA duplicato): {json_file.name}")
            # Sposta il file in cvs_processed
            json_file.rename(processed_folder / json_file.name)

        elif user_id and user_id in user_id_to_index:
            if sha256 and sha256 not in existing_sha256:
                files_to_update.append((json_file, user_id, sha256, user_id_to_index[user_id]))
                print(f"  UPDATE: {json_file.name} -> {user_id}")
                # Sposta il file in cvs_processed
                json_file.rename(processed_folder / json_file.name)
            else:
                files_skipped_both.append((json_file.name, user_id, sha256))
                print(f"  SKIP (duplicato): {json_file.name}")
                # Sposta il file in cvs_processed
                json_file.rename(processed_folder / json_file.name)
        else:
            files_to_add.append(json_file)

    print(f"\nRisultato:")
    print(f"  Nuovi: {len(files_to_add)}")
    print(f"  Da aggiornare: {len(files_to_update)}")
    print(f"  Saltati: {len(files_skipped_sha) + len(files_skipped_both)}")
    if files_no_identifiers:
        print(f"  Senza identificatori: {len(files_no_identifiers)}")

    if not files_to_add and not files_to_update:
        print("\nNessun file da processare")
        return True

    rows_to_add = []
    errors = []

    if files_to_add:
        print(f"\nProcessamento {len(files_to_add)} nuovi CV...")

        for json_file in files_to_add:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # MODIFICATO: passiamo all_known_tags
                row = json_to_row(data, json_file.name, all_known_tags)
                rows_to_add.append(row)

                user_id = row['user_id'] or 'N/A'
                print(f"  {json_file.name} -> {user_id}")

                # Sposta il file in cvs_processed
                json_file.rename(processed_folder / json_file.name)

            except Exception as e:
                errors.append((json_file.name, str(e)))
                print(f"  ERRORE: {json_file.name} - {e}")

    rows_to_update = []

    if files_to_update:
        print(f"\nAggiornamento {len(files_to_update)} CV esistenti...")

        for json_file, user_id, sha256, row_index in files_to_update:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                # MODIFICATO: passiamo all_known_tags
                row = json_to_row(data, json_file.name, all_known_tags)
                rows_to_update.append((row_index, row))

                print(f"  {json_file.name} -> {user_id}")

            except Exception as e:
                errors.append((json_file.name, str(e)))
                print(f"  ERRORE: {json_file.name} - {e}")
            else:
                # Sposta il file in cvs_processed SOLO dopo averlo letto e processato
                json_file.rename(processed_folder / json_file.name)

    output_path.mkdir(parents=True, exist_ok=True)

    if full_output_path.exists():
        existing_df = pd.read_csv(full_output_path, encoding='utf-8')

        for row_index, row_data in rows_to_update:
            for col, value in row_data.items():
                if col in existing_df.columns:
                    existing_df.at[row_index, col] = value
                else:
                    # NOVITÀ: se la colonna non esiste (nuovo tag), la creiamo
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

    # MODIFICATO: ordine colonne ora include i tag dinamici
    base_cols = [
        'user_id', 'source_file', 'processed_at', 'document_id', 'document_type', 'file_sha256',
        'pi_full_name', 'pi_email', 'pi_phone', 'pi_address', 'pi_city', 'pi_country',
        'pi_postal_code', 'pi_linkedin', 'pi_github', 'pi_website', 'summary',
        'experience', 'education', 'skills', 'languages', 'certifications', 'projects',
        'pref_desired_roles', 'pref_preferred_locations', 'pref_remote_preference',
        'pref_salary_expectation', 'pref_availability'
    ]
    
    # Aggiungiamo le colonne tag in ordine alfabetico
    tag_cols = sorted([f"tag_{tag}" for tag in all_known_tags])
    
    # Colonne finali: base + tag
    cols = base_cols + tag_cols
    
    # Manteniamo solo le colonne che esistono effettivamente nel DataFrame
    existing_cols = [c for c in cols if c in final_df.columns]
    final_df = final_df[existing_cols]

    final_df.to_csv(full_output_path, index=False, encoding='utf-8')

    print(f"\nCompletato: {full_output_path}")
    print(f"Nuove righe: {len(rows_to_add)}")
    print(f"Righe aggiornate: {len(rows_to_update)}")
    # if removed_count > 0:
    #     print(f"Righe eliminate: {removed_count}")
    print(f"Totale righe: {len(final_df)}")
    print(f"Colonne totali: {len(final_df.columns)} (di cui {len(tag_cols)} colonne tag)")

    if errors:
        print(f"\nErrori: {len(errors)}")
        for fname, error in errors:
            print(f"  {fname}: {error}")

    return True


if __name__ == "__main__":
    process_files(INPUT_FOLDER, OUTPUT_FOLDER, OUTPUT_FILENAME)
