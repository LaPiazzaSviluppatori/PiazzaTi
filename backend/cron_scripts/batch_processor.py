#!/usr/bin/env python3
"""
Batch Processor per CV/JD con pipeline NLP completa
Struttura progetto attesa:

project_root/
    cron_scripts/
        batch_processor.py  ← questo file
    NLP/
        cv_json_to_dataset_processor.py
        normalizzatore.py
        embed_generator.py
        Matching.py
        Dataset/
        data/

Questo script usa SUBPROCESS per eseguire gli script sotto NLP (modalità B).
"""

from __future__ import annotations

import sys
import argparse
from pathlib import Path
from datetime import datetime
import logging
import subprocess
from typing import List

# -----------------------------
# Logging
# -----------------------------
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    handlers=[logging.StreamHandler()]
)
logger = logging.getLogger(__name__)

# -----------------------------
# Paths (assume cron_scripts/ is current file parent)
# project_root/
#     cron_scripts/
#     NLP/
# -----------------------------
HERE = Path(__file__).resolve().parent            # cron_scripts/

# Calcolo robusto della root del progetto:
# - in ambiente host:   .../PiazzaTi/backend/cron_scripts -> PROJECT_ROOT = .../PiazzaTi
# - in container:       /app/cron_scripts              -> PROJECT_ROOT = /app
parent1 = HERE.parent
parent2 = parent1.parent
if (parent1 / "NLP").exists():
    PROJECT_ROOT = parent1
else:
    PROJECT_ROOT = parent2

NLP_PATH = PROJECT_ROOT / "NLP"
BACKEND_PATH = PROJECT_ROOT / "backend"

logger.info("Project root: %s", PROJECT_ROOT)
logger.info("NLP path: %s", NLP_PATH)
logger.info("Backend path: %s", BACKEND_PATH)

# Ensure NLP_PATH exists
if not NLP_PATH.exists():
    logger.error("NLP folder non trovata: %s", NLP_PATH)
    # Non uscire subito: permettiamo all'utente di lanciare per testare

# Utility to run python scripts under NLP/ with subprocess

def run_nlp_script(script_name: str, args: List[str] | None = None) -> subprocess.CompletedProcess:
    """Esegue lo script Python presente sotto NLP_PATH con lo stesso interprete.
    Ritorna CompletedProcess.
    """
    script_path = NLP_PATH / script_name
    if not script_path.exists():
        raise FileNotFoundError(f"Script non trovato: {script_path}")

    cmd = [sys.executable, str(script_path)]
    if args:
        cmd.extend(args)

    logger.info("Eseguo: %s", " ".join(cmd))
    result = subprocess.run(cmd, cwd=str(NLP_PATH), capture_output=True, text=True)
    if result.returncode != 0:
        logger.error("Script %s fallito (code %d). stderr:%s", script_name, result.returncode, result.stderr.strip())
    else:
        logger.info("Script %s completato. stdout len=%d", script_name, len(result.stdout))
    return result

# -----------------------------
# JD Batch Processor
# -----------------------------
class JDBatchProcessor:
    def __init__(self):
        self.jds_path = NLP_PATH / "data" / "jds"
        self.dataset_path = NLP_PATH / "Dataset"
        self.output_path = self.dataset_path / "normalized"
        self.csv_script = "jd_json_to_dataset_processor.py"

    def process(self):
        logger.info("%s", "=" * 80)
        logger.info("BATCH PROCESSING JD - PIPELINE NLP COMPLETA")
        logger.info("%s", "=" * 80)

        # Step 1: JSON -> CSV
        logger.info("Step 1: Conversione JSON → CSV JD")
        try:
            run_nlp_script(self.csv_script)
        except Exception as e:
            logger.exception("Errore Step 1 JD: %s", e)
            return

        # Step 2: Normalizzazione
        logger.info("Step 2: Normalizzazione JD")
        try:
            run_nlp_script("normalizzatore.py")
        except Exception as e:
            logger.exception("Errore Step 2 JD: %s", e)

        # Step 3: Embeddings
        logger.info("Step 3: Generazione Embeddings JD")
        try:
            run_nlp_script("embed_generator.py")
        except Exception as e:
            logger.exception("Errore Step 3 JD: %s", e)

        logger.info("Pipeline JD completata")

# -----------------------------
# CV Batch Processor
# -----------------------------
class CVBatchProcessor:
    def __init__(self):
        self.cvs_path = NLP_PATH / "data" / "cvs"
        # Also consider cvs_processed where files may be moved after parsing
        self.cvs_processed_path = NLP_PATH / "data" / "cvs_processed"
        self.dataset_path = NLP_PATH / "Dataset"
        self.output_path = self.dataset_path / "normalized"
        self.cv_json_script = "cv_json_to_dataset_processor.py"
        self.normalizer_script = "normalizzatore.py"
        self.embed_script = "embed_generator.py"

        # ensure folders exist
        self.dataset_path.mkdir(parents=True, exist_ok=True)
        self.output_path.mkdir(parents=True, exist_ok=True)

    def process_date_range(self, start_date: str | None = None, end_date: str | None = None):
        logger.info("%s", "=" * 80)
        logger.info("BATCH PROCESSING CV - PIPELINE NLP COMPLETA")
        logger.info("%s", "=" * 80)

        if start_date is None:
            start_date = datetime.now().date().isoformat()
        if end_date is None:
            end_date = start_date

        # validate
        try:
            sd = datetime.fromisoformat(start_date).date()
            ed = datetime.fromisoformat(end_date).date()
        except Exception as e:
            logger.error("Formato data non valido: %s", e)
            return
        if sd > ed:
            logger.error("start_date deve essere <= end_date")
            return

        logger.info("Processing range: %s -> %s", sd.isoformat(), ed.isoformat())

        date_folders = self._find_date_folders(sd, ed)
        if not date_folders:
            logger.warning("Nessun CV trovato per il range %s - %s", sd.isoformat(), ed.isoformat())
            return

        total_files = sum(len(list(folder.glob("*.json"))) for folder in date_folders)
        logger.info("Trovati %d CV in %d cartelle", total_files, len(date_folders))
        if total_files == 0:
            logger.warning("Nessun file JSON da processare")
            return

        try:
            logger.info("Step 1: Conversione JSON -> CSV")
            self._json_to_csv_pipeline(date_folders)

            logger.info("Step 2: Normalizzazione")
            self._normalization_pipeline()

            logger.info("Step 3: Generazione embeddings")
            self._embeddings_pipeline()

            logger.info("Pipeline completata con successo")
            self._print_summary()

            # Step 4: Matching (una sola volta, se Matching.py presente)
            matching_script = NLP_PATH / "Matching.py"
            if matching_script.exists():
                logger.info("Eseguo Matching CV-JD")
                run_nlp_script("Matching.py")
            else:
                logger.warning("Matching.py non trovato: %s", matching_script)

        except Exception as e:
            logger.exception("Errore durante processing: %s", e)

    def _find_date_folders(self, start_date, end_date) -> List[Path]:
        folders: List[Path] = []
        # Consider both `cvs` and `cvs_processed` for legacy and processed files.
        bases = [self.cvs_path, self.cvs_processed_path]
        any_base_exists = any(b.exists() for b in bases)
        if not any_base_exists:
            logger.warning("Nessuna cartella cvs trovata tra: %s, %s", self.cvs_path, self.cvs_processed_path)
            return folders

        # Modalità legacy: cerca sottocartelle con nome data (YYYY-MM-DD)
        for base in bases:
            if not base.exists():
                continue
            for child in sorted(base.iterdir()):
                if not child.is_dir():
                    continue
                try:
                    d = datetime.fromisoformat(child.name).date()
                except Exception:
                    continue
                if start_date <= d <= end_date:
                    folders.append(child)

        # Nuova modalità (flat): se non sono state trovate cartelle per date,
        # cerca JSON direttamente sotto `cvs` e `cvs_processed` e usa le cartelle
        # che contengono JSON come bucket singoli.
        if not folders:
            json_count = 0
            for base in bases:
                if not base.exists():
                    continue
                js = list(base.glob("*.json"))
                json_count += len(js)
                if js:
                    logger.info("Rilevata struttura flat in %s ( %d JSON ).", base, len(js))
                    folders.append(base)
            if json_count == 0:
                logger.warning("Nessun JSON da processare nelle cartelle cvs/cvs_processed")

        return folders

    def _json_to_csv_pipeline(self, date_folders: List[Path]):
        # In modalità B usiamo sempre lo script che si occupa di leggere data/cvs
        script_name = self.cv_json_script
        if not (NLP_PATH / script_name).exists():
            raise FileNotFoundError(f"cv_json_to_dataset_processor.py non trovato sotto {NLP_PATH}")
        # Possiamo passare opzionalmente il range a script
        # Se lo script supporta args, potrebbe leggerli; qui non forziamo param
        run_nlp_script(script_name)

    def _normalization_pipeline(self):
        # controlla esistenza input CSV (nome comune: cv_dataset.csv)
        input_csv = self.dataset_path / "cv_dataset.csv"
        if not input_csv.exists():
            raise FileNotFoundError(f"CV dataset non trovato: {input_csv}")
        logger.info("Input CSV: %s (%d KB)", input_csv, input_csv.stat().st_size // 1024)

        # Esegui normalizzatore (script)
        run_nlp_script(self.normalizer_script)

        output_csv = self.output_path / "cv_dataset_normalized.csv"
        if not output_csv.exists():
            raise FileNotFoundError(f"Output normalizzazione non trovato: {output_csv}")
        logger.info("CSV normalizzato: %s (%d KB)", output_csv, output_csv.stat().st_size // 1024)

    def _embeddings_pipeline(self):
        normalized_csv = self.output_path / "cv_dataset_normalized.csv"
        if not normalized_csv.exists():
            raise FileNotFoundError(f"CSV normalizzato non trovato: {normalized_csv}")
        logger.info("Input normalizzato: %s", normalized_csv)

        run_nlp_script(self.embed_script)

        embeddings_file = NLP_PATH / "embeddings" / "cv_embeddings.csv"
        if embeddings_file.exists():
            logger.info("Embeddings generati: %s (%d KB)", embeddings_file, embeddings_file.stat().st_size // 1024)
        else:
            logger.warning("File embeddings non trovato: %s", embeddings_file)

    def _print_summary(self):
        logger.info("--- RIEPILOGO ---")
        try:
            norm = self.output_path / 'cv_dataset_normalized.csv'
            emb = NLP_PATH / 'embeddings' / 'cv_embeddings.csv'
            logger.info('CSV normalizzato: %s', norm if norm.exists() else 'MANCANTE')
            logger.info('Embeddings: %s', emb if emb.exists() else 'MANCANTE')
        except Exception:
            logger.exception('Errore durante riepilogo')

# -----------------------------
# CLI
# -----------------------------

def main():
    parser = argparse.ArgumentParser(description='Batch processor per CV con pipeline NLP')
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--process-today', action='store_true', help='Processa CV di oggi')
    group.add_argument('--process-date', type=str, metavar='YYYY-MM-DD', help='Processa CV di una data specifica')
    group.add_argument('--process-range', nargs=2, metavar=('START', 'END'), help='Processa CV in un range di date')
    group.add_argument('--process-all', action='store_true', help='Processa tutti i CV disponibili')
    group.add_argument('--process-jd', action='store_true', help='Esegui pipeline JD')

    args = parser.parse_args()

    if args.process_jd:
        JDBatchProcessor().process()
        return

    processor = CVBatchProcessor()

    if args.process_today:
        processor.process_date_range()
    elif args.process_date:
        processor.process_date_range(args.process_date, args.process_date)
    elif args.process_range:
        processor.process_date_range(args.process_range[0], args.process_range[1])
    elif args.process_all:
        # In presenza di struttura legacy a cartelle data, processa
        # dall'intervallo minimo-massimo. Con struttura flat, _find_date_folders
        # restituirà direttamente [cvs_path] ignorando le date.
        processor.process_date_range()


if __name__ == '__main__':
    main()
    # Nessun codice aggiuntivo necessario qui.