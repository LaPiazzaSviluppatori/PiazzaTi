#!/usr/bin/env python3

import json
import hashlib
import logging
import sys
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Tuple
import warnings

# Configura PRIMA la cache HuggingFace in una directory sicuramente scrivibile
# (serve che sia fatto prima di importare sentence_transformers / transformers)
HF_CACHE_DIR = Path(os.getenv("HF_HOME", "/opt/piazzati/hf-cache"))
HF_CACHE_DIR.mkdir(parents=True, exist_ok=True)
os.environ["HF_HOME"] = str(HF_CACHE_DIR)
os.environ.setdefault("HF_HUB_CACHE", str(HF_CACHE_DIR / "hub"))
os.environ.setdefault("TRANSFORMERS_CACHE", str(HF_CACHE_DIR / "transformers"))

import pandas as pd
import numpy as np
from sentence_transformers import SentenceTransformer

warnings.filterwarnings('ignore')

if '__file__' in globals():
    BASE_DIR = Path(__file__).parent
else:
    BASE_DIR = Path(os.getcwd())

DATASET_DIR = BASE_DIR / "Dataset" / "normalized"
EMBEDDINGS_DIR = BASE_DIR / "embeddings"

CV_INPUT = DATASET_DIR / "cv_dataset_normalized.csv"
JD_INPUT = DATASET_DIR / "jd_dataset_normalized.csv"
CV_OUTPUT = EMBEDDINGS_DIR / "cv_embeddings.csv"
JD_OUTPUT = EMBEDDINGS_DIR / "jd_embeddings.csv"
METADATA_OUTPUT = EMBEDDINGS_DIR / "embedding_metadata.json"

MODEL_NAME = "sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2"
MODEL_DIM = 384
BATCH_SIZE = 32

CV_FIELDS = ["summary", "experience", "skills"]
JD_FIELDS = ["title", "description", "requirements", "nice_to_have"]

LOG_DIR = BASE_DIR / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)
LOG_FILE = LOG_DIR / "embed_generator.log"
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler(str(LOG_FILE)),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger(__name__)


def setup_directories():
    EMBEDDINGS_DIR.mkdir(parents=True, exist_ok=True)


def compute_text_hash(text: str) -> str:
    return hashlib.sha256(text.encode('utf-8')).hexdigest()


def safe_str(value) -> str:
    if pd.isna(value) or value is None:
        return ""
    return str(value).strip()


def prepare_text(text: str, max_length: int = 10000) -> str:
    cleaned = " ".join(text.split())
    if len(cleaned) > max_length:
        cleaned = cleaned[:max_length]
    return cleaned


def concatenate_cv_fields(row: pd.Series) -> str:
    parts = []

    summary = safe_str(row.get('summary', ''))
    if summary:
        parts.append(f"Summary: {summary}")

    experience = safe_str(row.get('experience', ''))
    if experience:
        parts.append(f"Experience: {experience}")

    skills = safe_str(row.get('skills', ''))
    if skills:
        parts.append(f"Skills: {skills}")

    return prepare_text(" | ".join(parts))


def concatenate_jd_fields(row: pd.Series) -> str:
    parts = []

    title = safe_str(row.get('title', ''))
    if title:
        parts.append(f"Title: {title}")

    description = safe_str(row.get('description', ''))
    if description:
        parts.append(f"Description: {description}")

    requirements = safe_str(row.get('requirements', ''))
    if requirements:
        parts.append(f"Requirements: {requirements}")

    nice_to_have = safe_str(row.get('nice_to_have', ''))
    if nice_to_have:
        parts.append(f"Nice to have: {nice_to_have}")

    return prepare_text(" | ".join(parts))


def compute_drift_metrics(embeddings: np.ndarray) -> Dict:

    if embeddings is None or len(embeddings) == 0 or (hasattr(embeddings, 'shape') and embeddings.shape == (0,)):
        return {
            "mean_norm": 0.0,
            "std_norm": 0.0,
            "min_norm": 0.0,
            "max_norm": 0.0,
            "quartiles": {"q25": 0.0, "q50": 0.0, "q75": 0.0}
        }

    norms = np.linalg.norm(embeddings, axis=1)
    return {
        "mean_norm": float(np.mean(norms)),
        "std_norm": float(np.std(norms)),
        "min_norm": float(np.min(norms)),
        "max_norm": float(np.max(norms)),
        "quartiles": {
            "q25": float(np.percentile(norms, 25)),
            "q50": float(np.percentile(norms, 50)),
            "q75": float(np.percentile(norms, 75))
        }
    }


def load_model() -> SentenceTransformer:
    logger.info(f"Loading model: {MODEL_NAME}")
    model = SentenceTransformer(MODEL_NAME)
    logger.info(f"Model loaded on device: {model.device}")
    return model


def generate_embeddings(
    texts: List[str],
    model: SentenceTransformer,
    batch_size: int = BATCH_SIZE
) -> np.ndarray:

    embeddings = model.encode(
        texts,
        batch_size=batch_size,
        show_progress_bar=True,
        convert_to_numpy=True,
        normalize_embeddings=True
    )

    return embeddings


def process_cv_dataset() -> Tuple[pd.DataFrame, Dict]:
    logger.info("Processing CV dataset")

    if not CV_INPUT.exists():
        raise FileNotFoundError(f"CV dataset not found: {CV_INPUT}")

    df = pd.read_csv(CV_INPUT)
    logger.info(f"Loaded {len(df)} CVs")

    df['text_content'] = df.apply(concatenate_cv_fields, axis=1)

    # Gestione robusta anche per DataFrame vuoti
    if 'text_content' in df.columns:
        empty_mask = df['text_content'].astype(str).str.strip() == ''
    else:
        empty_mask = pd.Series([], dtype=bool)
    if empty_mask.any():
        logger.warning(f"Skipping {empty_mask.sum()} empty JDs")
        df = df[~empty_mask].reset_index(drop=True)

    texts = df['text_content'].tolist()
    model = load_model()
    embeddings = generate_embeddings(texts, model)

    df['text_hash'] = df['text_content'].apply(compute_text_hash)
    df['embedding_vector'] = [json.dumps(emb.tolist()) for emb in embeddings]
    df['model_name'] = MODEL_NAME
    df['model_dim'] = MODEL_DIM
    df['created_at'] = datetime.now().isoformat()
    df['document_type'] = 'cv'  

    stats = compute_drift_metrics(embeddings)
    stats['count'] = len(df)
    stats['empty_skipped'] = empty_mask.sum()

    logger.info(f"Generated {len(df)} CV embeddings")

    return df, stats


def process_jd_dataset() -> Tuple[pd.DataFrame, Dict]:
    logger.info("Processing JD dataset")

    if not JD_INPUT.exists():
        logger.warning(f"JD dataset not found: {JD_INPUT}")
        # Restituisci DataFrame vuoto e stats nulle
        empty_stats = {
            "mean_norm": 0.0,
            "std_norm": 0.0,
            "min_norm": 0.0,
            "max_norm": 0.0,
            "quartiles": {"q25": 0.0, "q50": 0.0, "q75": 0.0},
            "count": 0,
            "empty_skipped": 0
        }
        return pd.DataFrame(), empty_stats

    df = pd.read_csv(JD_INPUT)
    logger.info(f"Loaded {len(df)} JDs")

    if df.empty:
        logger.warning("JD dataset is empty. Skipping embedding generation for JD.")
        empty_stats = {
            "mean_norm": 0.0,
            "std_norm": 0.0,
            "min_norm": 0.0,
            "max_norm": 0.0,
            "quartiles": {"q25": 0.0, "q50": 0.0, "q75": 0.0},
            "count": 0,
            "empty_skipped": 0
        }
        return df, empty_stats

    df['text_content'] = df.apply(concatenate_jd_fields, axis=1)

    empty_mask = df['text_content'].astype(str).str.strip() == ''
    if empty_mask.any():
        logger.warning(f"Skipping {empty_mask.sum()} empty JDs")
        df = df[~empty_mask].reset_index(drop=True)

    if df.empty:
        logger.warning("All JD rows are empty after filtering. Skipping embedding generation for JD.")
        empty_stats = {
            "mean_norm": 0.0,
            "std_norm": 0.0,
            "min_norm": 0.0,
            "max_norm": 0.0,
            "quartiles": {"q25": 0.0, "q50": 0.0, "q75": 0.0},
            "count": 0,
            "empty_skipped": empty_mask.sum()
        }
        return df, empty_stats

    texts = df['text_content'].tolist()
    model = load_model()
    embeddings = generate_embeddings(texts, model)

    df['text_hash'] = df['text_content'].apply(compute_text_hash)
    df['embedding_vector'] = [json.dumps(emb.tolist()) for emb in embeddings]
    df['model_name'] = MODEL_NAME
    df['model_dim'] = MODEL_DIM
    df['created_at'] = datetime.now().isoformat()
    df['document_type'] = 'jd'  

    stats = compute_drift_metrics(embeddings)
    stats['count'] = len(df)
    stats['empty_skipped'] = empty_mask.sum()

    logger.info(f"Generated {len(df)} JD embeddings")

    return df, stats


def save_embeddings(
    df: pd.DataFrame,
    output_path: Path,
    id_column: str,
    columns_to_save: List[str]
):
    df_output = df[columns_to_save].copy()
    df_output = df_output.sort_values(by=id_column).reset_index(drop=True)
    df_output.to_csv(output_path, index=False)
    logger.info(f"Saved {len(df_output)} embeddings to {output_path}")


def save_metadata(cv_stats: Dict, jd_stats: Dict):

    def convert_to_native(obj):
        if isinstance(obj, (np.integer, np.int64, np.int32)):
            return int(obj)
        elif isinstance(obj, (np.floating, np.float64, np.float32)):
            return float(obj)
        elif isinstance(obj, dict):
            return {key: convert_to_native(value) for key, value in obj.items()}
        elif isinstance(obj, (list, tuple)):
            return [convert_to_native(item) for item in obj]
        return obj

    metadata = {
        "model": {
            "name": MODEL_NAME,
            "dimensions": MODEL_DIM,
            "version": "1.0.0"
        },
        "generation": {
            "timestamp": datetime.now().isoformat(),
            "cv_count": int(cv_stats['count']),
            "jd_count": int(jd_stats['count']),
            "batch_size": BATCH_SIZE,
            "cv_empty_skipped": int(cv_stats.get('empty_skipped', 0)),
            "jd_empty_skipped": int(jd_stats.get('empty_skipped', 0))
        },
        "statistics": {
            "cv": convert_to_native({
                "mean_norm": cv_stats['mean_norm'],
                "std_norm": cv_stats['std_norm'],
                "min_norm": cv_stats['min_norm'],
                "max_norm": cv_stats['max_norm'],
                "quartiles": cv_stats['quartiles']
            }),
            "jd": convert_to_native({
                "mean_norm": jd_stats['mean_norm'],
                "std_norm": jd_stats['std_norm'],
                "min_norm": jd_stats['min_norm'],
                "max_norm": jd_stats['max_norm'],
                "quartiles": jd_stats['quartiles']
            })
        },
        "fields_used": {
            "cv": CV_FIELDS,
            "jd": JD_FIELDS
        }
    }

    with open(METADATA_OUTPUT, 'w', encoding='utf-8') as f:
        json.dump(metadata, f, indent=2, ensure_ascii=False)

    logger.info(f"Metadata saved to {METADATA_OUTPUT}")


def main():
    start_time = datetime.now()

    try:
        logger.info("Starting embedding generation pipeline")

        setup_directories()

        # === CV FLOW ===
        cv_df, cv_stats = process_cv_dataset()
        cv_columns = [
            'user_id',
            'document_type',
            'embedding_vector',
            'text_content',
            'model_name',
            'model_dim',
            'created_at',
            'text_hash'
        ]
        save_embeddings(cv_df, CV_OUTPUT, 'user_id', cv_columns)

        # === JD FLOW ===
        # Normalizza JD dataset
        try:
            from normalizzatore import normalize_jd_dataset, SkillOntology, DATASET_DIR, OUTPUT_DIR
            ontology_path = DATASET_DIR / "skill_ontology.json"
            input_jd = DATASET_DIR / "jd_dataset.csv"
            output_jd = OUTPUT_DIR / "jd_dataset_normalized.csv"
            ontology = SkillOntology(ontology_path)
            normalize_jd_dataset(input_jd, output_jd, ontology)
            logger.info(f"JD dataset normalizzato: {output_jd}")
        except Exception as e:
            logger.warning(f"JD normalization skipped or failed: {e}")

        # Genera embeddings JD
        jd_df, jd_stats = process_jd_dataset()
        jd_columns = [
            'jd_id',
            'document_type',
            'embedding_vector',
            'text_content',
            'model_name',
            'model_dim',
            'created_at',
            'text_hash'
        ]
        save_embeddings(jd_df, JD_OUTPUT, 'jd_id', jd_columns)

        save_metadata(cv_stats, jd_stats)

        duration = (datetime.now() - start_time).total_seconds()
        logger.info(f"Pipeline completed in {duration:.2f}s")

    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    main()
