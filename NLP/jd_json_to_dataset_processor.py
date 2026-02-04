# -*- coding: utf-8 -*-
"""
jd_to_csv_processor.py
Converte file JSON JD in un dataset CSV tabulare
Con controllo duplicati e pulizia JD eliminate

AGGIORNAMENTO v2: aggiunto supporto per campo company_name
AGGIORNAMENTO v1: aggiunto supporto per campo min_experience_years
"""

import json
from pathlib import Path
from typing import List, Dict, Set
from datetime import datetime
import pandas as pd


INPUT_FOLDER = "data/jds"
OUTPUT_FOLDER = "Dataset"
OUTPUT_FILENAME = "jd_dataset.csv"

ARRAY_SEP = " | "
LIST_SEP = ", "


def get_active_jd_ids(input_path: Path) -> Set[str]:
    """
    Estrae tutti i jd_id dai file JSON presenti nella cartella.
    
    Scopo: Identificare quali JD sono ancora "attive" (hanno un file JSON).
    Questo serve per la pulizia successiva dei record orfani nel CSV.
    """
    active_jds = set()

    json_files = list(input_path.glob("*.json"))

    for json_file in json_files:
        try:
            with open(json_file, 'r', encoding='utf-8') as f:
                data = json.load(f)

            jd_id = str(data.get('jd_id', '')) if data.get('jd_id') else ''
            if jd_id:
                active_jds.add(jd_id)
        except:
            continue

    return active_jds


def clean_deleted_jds(output_path: Path, active_jd_ids: Set[str]) -> int:
    """
    Rimuove dal dataset le JD che non hanno più file JSON.
    
    Scopo: Mantenere il CSV sincronizzato con i file JSON.
    Se un file JSON viene eliminato, la riga corrispondente nel CSV
    deve essere rimossa per evitare dati obsoleti.
    """
    if not output_path.exists():
        return 0

    try:
        df = pd.read_csv(output_path, encoding='utf-8')

        if 'jd_id' not in df.columns:
            print("  Colonna jd_id non trovata nel dataset")
            return 0

        original_count = len(df)

        deleted_jds = []
        for idx, jd_id in enumerate(df['jd_id']):
            if pd.notna(jd_id) and str(jd_id).strip():
                if str(jd_id) not in active_jd_ids:
                    deleted_jds.append(str(jd_id))

        if deleted_jds:
            df = df[df['jd_id'].isin(active_jd_ids) | df['jd_id'].isna()]
            df.to_csv(output_path, index=False, encoding='utf-8')

            removed_count = original_count - len(df)

            print(f"  JD rimosse: {len(set(deleted_jds))}")
            print(f"  Righe eliminate: {removed_count}")

            if len(deleted_jds) <= 10:
                for jd_id in set(deleted_jds):
                    print(f"    - {jd_id}")

            return removed_count
        else:
            print("  Nessuna JD da rimuovere")
            return 0

    except Exception as e:
        print(f"  Errore durante la pulizia: {e}")
        return 0


def get_existing_jd_ids(output_path: Path) -> Dict[str, int]:
    """
    Legge il CSV esistente e restituisce i jd_id già presenti.
    
    Scopo: Permettere l'identificazione di duplicati.
    Restituisce un dizionario {jd_id: indice_riga} per sapere
    quali JD sono già nel dataset e dove si trovano (per aggiornamenti).
    """
    if not output_path.exists():
        return {}

    try:
        df = pd.read_csv(output_path, encoding='utf-8')

        jd_id_to_index = {}
        if 'jd_id' in df.columns:
            for idx, jd_id in enumerate(df['jd_id']):
                if pd.notna(jd_id) and str(jd_id).strip():
                    jd_id_to_index[str(jd_id)] = idx

        return jd_id_to_index

    except Exception as e:
        print(f"Avviso: impossibile leggere il CSV esistente: {e}")
        return {}


def extract_jd_id_from_json(json_path: Path) -> str:
    """
    Estrae il jd_id da un file JSON.
    
    Scopo: Lettura veloce dell'identificatore senza caricare tutto il JSON.
    Usato nella fase di classificazione per determinare se un file
    è nuovo o va aggiornato.
    """
    try:
        with open(json_path, 'r', encoding='utf-8') as f:
            data = json.load(f)

        jd_id = str(data.get('jd_id', '')) if data.get('jd_id') else ''
        return jd_id

    except Exception as e:
        print(f"  Errore lettura da {json_path.name}: {e}")
        return ''


def flatten_location(data: Dict) -> Dict:
    """
    Appiattisce il campo location.
    
    Scopo: Trasformare un oggetto nested JSON in colonne flat per il CSV.
    
    Input JSON:
        "location": {"city": "Milan", "country": "IT", "remote": true}
    
    Output Dict:
        {"location_city": "Milan", "location_country": "IT", "location_remote": "Yes"}
    """
    if not data:
        return {
            'location_city': '',
            'location_country': '',
            'location_remote': ''
        }

    return {
        'location_city': data.get('city', ''),
        'location_country': data.get('country', ''),
        'location_remote': 'Yes' if data.get('remote') else 'No'
    }


def flatten_constraints(data: Dict) -> Dict:
    """
    Appiattisce il campo constraints.
    
    Scopo: Convertire i vincoli della posizione in colonne leggibili.
    
    Input JSON:
        "constraints": {
            "visa": false,
            "relocation": true,
            "seniority": "senior",
            "languages_min": [{"lang": "english", "level": "C1"}]
        }
    
    Output Dict:
        {
            "constraints_visa": "Not required",
            "constraints_relocation": "Available",
            "constraints_seniority": "senior",
            "constraints_languages": "english (C1)"
        }
    
    Note:
    - visa e relocation vengono convertiti da boolean a stringhe human-readable
    - languages_min viene concatenato in formato "lingua (livello)"
    """
    if not data:
        return {
            'constraints_visa': '',
            'constraints_relocation': '',
            'constraints_seniority': '',
            'constraints_languages': ''
        }

    # Costruisce la stringa delle lingue richieste
    languages = []
    if 'languages_min' in data and data['languages_min']:
        for lang in data['languages_min']:
            lang_name = lang.get('lang', '')
            level = lang.get('level', '')
            languages.append(f"{lang_name} ({level})")

    return {
        'constraints_visa': 'Required' if data.get('visa') else 'Not required',
        'constraints_relocation': 'Available' if data.get('relocation') else 'Not available',
        'constraints_seniority': data.get('seniority', ''),
        'constraints_languages': LIST_SEP.join(languages)
    }


def flatten_dei_requirements(data: Dict) -> Dict:
    """
    Appiattisce il campo dei_requirements (Diversity, Equity & Inclusion).
    
    Scopo: Estrarre i target di bilanciamento per genere e gruppi sottorappresentati.
    
    Input JSON:
        "dei_requirements": {
            "target_balance": {"gender": 0.5, "underrepresented": 0.3}
        }
    
    Output Dict:
        {"dei_gender_target": "0.5", "dei_underrepresented_target": "0.3"}
    """
    if not data or 'target_balance' not in data:
        return {
            'dei_gender_target': '',
            'dei_underrepresented_target': ''
        }

    target = data.get('target_balance', {})

    return {
        'dei_gender_target': str(target.get('gender', '')),
        'dei_underrepresented_target': str(target.get('underrepresented', ''))
    }


def flatten_metadata(data: Dict) -> Dict:
    """
    Appiattisce il campo metadata.
    
    Scopo: Estrarre informazioni su salario e tipo di contratto.
    
    Input JSON:
        "metadata": {
            "salary_range": {"min": 55000, "max": 70000, "currency": "EUR"},
            "contract": "full_time"
        }
    
    Output Dict:
        {
            "salary_min": "55000",
            "salary_max": "70000", 
            "salary_currency": "EUR",
            "contract": "full_time"
        }
    """
    if not data:
        return {
            'salary_min': '',
            'salary_max': '',
            'salary_currency': '',
            'contract': ''
        }

    salary_range = data.get('salary_range', {})

    return {
        'salary_min': str(salary_range.get('min', '')) if salary_range else '',
        'salary_max': str(salary_range.get('max', '')) if salary_range else '',
        'salary_currency': salary_range.get('currency', '') if salary_range else '',
        'contract': data.get('contract', '')
    }


def json_to_row(data: Dict, source_file: str) -> Dict:
    """
    Trasforma un JSON JD in una riga del dataset.

    Scopo: Funzione principale di conversione che orchestra tutte le
    funzioni di flattening e produce una riga pronta per il CSV.
    
    CHANGELOG:
    - v2: Aggiunto campo company_name (nome dell'azienda che pubblica la JD)
    - v1: Aggiunto campo min_experience_years
    
    Ordine dei campi nel dizionario risultante:
    1. Identificatori: jd_id, company_name
    2. Metadati processing: source_file, processed_at
    3. Info posizione: title, department
    4. Location: city, country, remote
    5. Contenuto: description, min_experience_years, requirements, nice_to_have
    6. Vincoli: visa, relocation, seniority, languages
    7. DEI: target di bilanciamento
    8. Compensation: salary range, contract type
    """
    # NUOVO CAMPO v2: company_name
    # Rappresenta il nome dell'azienda che pubblica la Job Description
    # Campo opzionale: se non presente, restituisce stringa vuota
    company_name = data.get('company_name', '')
    
    # Campo v1: min_experience_years
    # Anni di esperienza minimi richiesti come numero intero
    min_exp = data.get('min_experience_years')
    min_experience_years = str(min_exp) if min_exp is not None else ''

    row = {
        # Identificatori
        'jd_id': data.get('jd_id', ''),
        'company_name': company_name,  # NUOVO CAMPO v2
        
        # Metadati di processing
        'source_file': source_file,
        'processed_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        
        # Informazioni sulla posizione
        'title': data.get('title', ''),
        'department': data.get('department', ''),
        
        # Contenuto testuale
        'description': data.get('description', ''),
        'min_experience_years': min_experience_years,  # Campo v1
        
        # Array convertiti in stringhe separate da virgola
        'requirements': LIST_SEP.join(data.get('requirements', [])),
        'nice_to_have': LIST_SEP.join(data.get('nice_to_have', []))
    }

    # Aggiunge i campi nested appiattiti
    row.update(flatten_location(data.get('location', {})))
    row.update(flatten_constraints(data.get('constraints', {})))
    row.update(flatten_dei_requirements(data.get('dei_requirements', {})))
    row.update(flatten_metadata(data.get('metadata', {})))

    return row


def process_files(input_dir: str, output_dir: str, output_file: str):
    """
    Funzione principale che orchestra l'intero processo di conversione.
    
    Flusso di elaborazione:
    1. Validazione: Verifica esistenza cartella input e presenza file JSON
    2. Pulizia: Rimuove dal CSV le JD i cui file JSON sono stati eliminati
    3. Classificazione: Identifica file nuovi vs da aggiornare
    4. Processing: Converte ogni JSON in una riga CSV
    5. Merge: Combina righe esistenti con nuove/aggiornate
    6. Salvataggio: Scrive il CSV finale con ordine colonne corretto
    """
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    full_output_path = output_path / output_file

    # Validazione input
    if not input_path.exists():
        print(f"Errore: cartella {input_dir} non trovata")
        return False

    json_files = list(input_path.glob("*.json"))

    if not json_files:
        print(f"Nessun file JSON trovato in {input_dir}")
        return False

    print(f"Trovati {len(json_files)} file JSON")

    # FASE 1: Pulizia JD eliminate
    print(f"\nControllo JD eliminate...")
    active_jd_ids = get_active_jd_ids(input_path)
    print(f"  JD attive nei JSON: {len(active_jd_ids)}")

    removed_count = clean_deleted_jds(full_output_path, active_jd_ids)

    # FASE 2: Identificazione duplicati
    print(f"\nControllo duplicati nel dataset esistente...")
    jd_id_to_index = get_existing_jd_ids(full_output_path)

    if jd_id_to_index:
        print(f"  JD ID unici: {len(jd_id_to_index)}")
    else:
        print(f"  Nessun dataset esistente")

    # FASE 3: Classificazione file
    print(f"\nAnalisi file JSON...")

    files_to_add = []      # File nuovi (jd_id non presente nel CSV)
    files_to_update = []   # File da aggiornare (jd_id già presente)
    files_no_id = []       # File senza jd_id (verranno comunque aggiunti)

    for json_file in json_files:
        jd_id = extract_jd_id_from_json(json_file)

        if not jd_id:
            files_no_id.append(json_file.name)
            files_to_add.append(json_file)

        elif jd_id in jd_id_to_index:
            files_to_update.append((json_file, jd_id, jd_id_to_index[jd_id]))
            print(f"  UPDATE: {json_file.name} -> {jd_id}")

        else:
            files_to_add.append(json_file)

    print(f"\nRisultato:")
    print(f"  Nuove: {len(files_to_add)}")
    print(f"  Da aggiornare: {len(files_to_update)}")
    if files_no_id:
        print(f"  Senza jd_id: {len(files_no_id)}")

    if not files_to_add and not files_to_update:
        print("\nNessun file da processare")
        if removed_count > 0:
            print(f"Dataset aggiornato: {removed_count} righe eliminate")
        return True

    # FASE 4: Processing file nuovi
    rows_to_add = []
    errors = []

    if files_to_add:
        print(f"\nProcessamento {len(files_to_add)} nuove JD...")

        for json_file in files_to_add:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                row = json_to_row(data, json_file.name)
                rows_to_add.append(row)

                jd_id = row['jd_id'] or 'N/A'
                company = row['company_name'] or 'N/A'
                print(f"  {json_file.name} -> {jd_id} ({company})")

            except Exception as e:
                errors.append((json_file.name, str(e)))
                print(f"  ERRORE: {json_file.name} - {e}")

    # FASE 5: Processing file da aggiornare
    rows_to_update = []

    if files_to_update:
        print(f"\nAggiornamento {len(files_to_update)} JD esistenti...")

        for json_file, jd_id, row_index in files_to_update:
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                row = json_to_row(data, json_file.name)
                rows_to_update.append((row_index, row))

                company = row['company_name'] or 'N/A'
                print(f"  {json_file.name} -> {jd_id} ({company})")

            except Exception as e:
                errors.append((json_file.name, str(e)))
                print(f"  ERRORE: {json_file.name} - {e}")

    # FASE 6: Merge e salvataggio
    output_path.mkdir(parents=True, exist_ok=True)

    if full_output_path.exists():
        existing_df = pd.read_csv(full_output_path, encoding='utf-8')

        # Gestione retrocompatibilità: aggiunta nuove colonne se non esistono
        # Questo permette di aggiornare dataset creati con versioni precedenti
        
        # Colonna v1: min_experience_years
        if 'min_experience_years' not in existing_df.columns:
            existing_df['min_experience_years'] = ''
            print("  Aggiunta nuova colonna 'min_experience_years' al dataset esistente")
        
        # NUOVO: Colonna v2: company_name
        if 'company_name' not in existing_df.columns:
            existing_df['company_name'] = ''
            print("  Aggiunta nuova colonna 'company_name' al dataset esistente")

        # Applica aggiornamenti alle righe esistenti
        for row_index, row_data in rows_to_update:
            for col, value in row_data.items():
                if col in existing_df.columns:
                    existing_df.at[row_index, col] = value

        # Aggiunge nuove righe
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

    # Definizione ordine colonne per il CSV finale
    # AGGIORNAMENTO v2: company_name inserito dopo jd_id
    cols = [
        # Identificatori
        'jd_id', 
        'company_name',  # NUOVO v2
        
        # Metadati processing
        'source_file', 
        'processed_at', 
        
        # Info posizione
        'title', 
        'department',
        
        # Location
        'location_city', 
        'location_country', 
        'location_remote',
        
        # Contenuto
        'description',
        'min_experience_years',  # v1
        'requirements', 
        'nice_to_have',
        
        # Vincoli
        'constraints_visa', 
        'constraints_relocation', 
        'constraints_seniority', 
        'constraints_languages',
        
        # DEI
        'dei_gender_target', 
        'dei_underrepresented_target',
        
        # Compensation
        'salary_min', 
        'salary_max', 
        'salary_currency', 
        'contract'
    ]

    # Filtra solo le colonne che esistono effettivamente nel DataFrame
    existing_cols = [c for c in cols if c in final_df.columns]
    final_df = final_df[existing_cols]

    final_df.to_csv(full_output_path, index=False, encoding='utf-8')

    # Report finale
    print(f"\nCompletato: {full_output_path}")
    print(f"Nuove righe: {len(rows_to_add)}")
    print(f"Righe aggiornate: {len(rows_to_update)}")
    if removed_count > 0:
        print(f"Righe eliminate: {removed_count}")
    print(f"Totale righe: {len(final_df)}")

    if errors:
        print(f"\nErrori: {len(errors)}")
        for fname, error in errors:
            print(f"  {fname}: {error}")

    return True


if __name__ == "__main__":
    process_files(INPUT_FOLDER, OUTPUT_FOLDER, OUTPUT_FILENAME)
