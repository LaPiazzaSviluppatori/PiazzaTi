#!/usr/bin/env python3
"""
Matching Engine per CV-JD similarity search.
Calcola similarità tra embeddings e prepara input per reranker.
"""

import json
import time
import warnings
from pathlib import Path
from typing import List, Tuple, Dict, Optional
from datetime import datetime
from functools import wraps

import numpy as np
import pandas as pd

warnings.filterwarnings('ignore')

# Config paths
BASE_DIR = Path.cwd()
# Use directories relative to the current working NLP folder (no duplicated "NLP" segment)
EMBEDDINGS_DIR = BASE_DIR / "embeddings"
OUTPUT_DIR = BASE_DIR / "match_results"

# Config params
TOP_K = 20
QUALITY_THRESHOLDS = {'excellent': 0.5, 'good': 0.3}
LATENCY_THRESHOLD_MS = 400


def track_latency(func):
    """Decorator per tracking latency delle operazioni."""
    @wraps(func)
    def wrapper(*args, **kwargs):
        start = time.perf_counter()
        result = func(*args, **kwargs)
        elapsed_ms = (time.perf_counter() - start) * 1000
        return result, elapsed_ms
    return wrapper


class LatencyTracker:
    """Traccia e analizza le latenze delle operazioni."""
    
    def __init__(self):
        self.measurements = []
    
    def record(self, operation: str, latency_ms: float):
        self.measurements.append({
            'operation': operation,
            'latency_ms': latency_ms,
            'timestamp': datetime.now()
        })
    
    def get_stats(self, operation: Optional[str] = None) -> Dict:
        if not self.measurements:
            return {}
        
        df = pd.DataFrame(self.measurements)
        if operation:
            df = df[df['operation'] == operation]
        
        if df.empty:
            return {}
        
        latencies = df['latency_ms'].values
        return {
            'count': len(latencies),
            'mean': float(np.mean(latencies)),
            'p50': float(np.percentile(latencies, 50)),
            'p95': float(np.percentile(latencies, 95)),
            'p99': float(np.percentile(latencies, 99)),
            'max': float(np.max(latencies))
        }
    
    def check_sla(self) -> Tuple[bool, float]:
        stats = self.get_stats('search')
        if not stats:
            return False, 0.0
        p95 = stats['p95']
        return p95 <= LATENCY_THRESHOLD_MS, p95


latency_tracker = LatencyTracker()


def cosine_similarity_batch(query: np.ndarray, corpus: np.ndarray) -> np.ndarray:
    """Calcola cosine similarity vettorizzata."""
    return (query @ corpus.T).squeeze()


def validate_embeddings(cv_df: pd.DataFrame, jd_df: pd.DataFrame):
    """Verifica compatibilità embeddings CV-JD."""
    # Check dimensioni
    cv_sample = json.loads(cv_df['embedding_vector'].iloc[0])
    jd_sample = json.loads(jd_df['embedding_vector'].iloc[0])
    
    if len(cv_sample) != len(jd_sample):
        raise ValueError(f"Dimension mismatch: CV={len(cv_sample)}, JD={len(jd_sample)}")
    
    # Check normalizzazione
    cv_norm = np.linalg.norm(cv_sample)
    jd_norm = np.linalg.norm(jd_sample)
    if not (0.95 <= cv_norm <= 1.05 and 0.95 <= jd_norm <= 1.05):
        print(f"Warning: Vectors not normalized (CV={cv_norm:.3f}, JD={jd_norm:.3f})")


@track_latency
def load_embeddings(csv_path: Path) -> Tuple[pd.DataFrame, np.ndarray]:
    """Carica embeddings da CSV."""
    df = pd.read_csv(csv_path)
    
    embeddings = []
    for emb_str in df['embedding_vector']:
        embeddings.append(np.array(json.loads(emb_str)))
    
    return df, np.vstack(embeddings)


def get_quality_label(score: float) -> str:
    """Determina quality label dal similarity score."""
    if score > QUALITY_THRESHOLDS['excellent']:
        return 'excellent'
    elif score > QUALITY_THRESHOLDS['good']:
        return 'good'
    return 'weak'


@track_latency
def find_top_k_matches(
    jd_embedding: np.ndarray,
    cv_embeddings: np.ndarray,
    cv_df: pd.DataFrame,
    k: int = TOP_K
) -> Tuple[List[Dict], str]:
    """Trova i top-K CV più simili alla JD."""
    
    # Calcola similarità
    similarities = cosine_similarity_batch(jd_embedding, cv_embeddings)
    
    # Top-K indices
    top_indices = np.argsort(similarities)[::-1][:k]
    
    # Build results
    matches = []
    for idx in top_indices:
        matches.append({
            'rank': len(matches) + 1,
            'user_id': cv_df.iloc[idx]['user_id'],
            'score': float(similarities[idx]),
            'preview': cv_df.iloc[idx]['text_content'][:200] + "...",
            'full_text': cv_df.iloc[idx]['text_content']
        })
    
    quality = get_quality_label(similarities[top_indices[0]])
    return matches, quality


def match_all_jds(
    jd_df: pd.DataFrame,
    jd_embeddings: np.ndarray,
    cv_df: pd.DataFrame,
    cv_embeddings: np.ndarray
) -> Dict[str, Dict]:
    """Esegue matching per tutte le JD."""
    
    results = {}
    
    for idx, row in jd_df.iterrows():
        jd_id = row['jd_id']
        jd_embedding = jd_embeddings[idx]
        
        # Find matches
        (matches, quality), latency_ms = find_top_k_matches(
            jd_embedding, cv_embeddings, cv_df
        )
        
        # Track latency
        latency_tracker.record('search', latency_ms)
        
        # Store result
        title = row['text_content'].split('|')[0].replace('Title:', '').strip()
        results[jd_id] = {
            'title': title,
            'preview': row['text_content'][:200] + "...",
            'matches': matches,
            'quality': quality,
            'latency_ms': latency_ms
        }
    
    return results


def prepare_reranker_data(
    results: Dict,
    cv_df: pd.DataFrame,
    jd_df: pd.DataFrame
) -> pd.DataFrame:
    """Prepara dataset per il reranker."""
    
    rows = []
    
    for jd_id, jd_info in results.items():
        jd_row = jd_df[jd_df['jd_id'] == jd_id].iloc[0]
        
        for match in jd_info['matches']:
            cv_row = cv_df[cv_df['user_id'] == match['user_id']].iloc[0]
            
            rows.append({
                'jd_id': jd_id,
                'user_id': match['user_id'],
                'rank': match['rank'],
                'cosine_similarity': match['score'],
                'jd_text': jd_row['text_content'],
                'cv_text': cv_row['text_content']
            })
    
    return pd.DataFrame(rows)


def save_results(results: Dict, output_dir: Path):
    """Salva risultati matching in JSON e CSV per reranker."""
    
    # JSON output
    json_output = {
        'metadata': {
            'timestamp': datetime.now().isoformat(),
            'top_k': TOP_K,
            'total_jds': len(results)
        },
        'matches': {}
    }
    
    for jd_id, info in results.items():
        json_output['matches'][jd_id] = {
            'title': info['title'],
            'quality': info['quality'],
            'latency_ms': info['latency_ms'],
            'candidates': [
                {
                    'rank': m['rank'],
                    'user_id': m['user_id'],
                    'score': m['score'],
                    'preview': m['preview']
                }
                for m in info['matches']
            ]
        }
    
    json_path = output_dir / "jd_cv_matches.json"
    with open(json_path, 'w', encoding='utf-8') as f:
        json.dump(json_output, f, indent=2, ensure_ascii=False)
    
    return json_path


def main():
    """Main execution."""
    
    # Setup
    OUTPUT_DIR.mkdir(exist_ok=True)
    
    # Load data
    print("Loading embeddings...")
    (cv_df, cv_embeddings), _ = load_embeddings(EMBEDDINGS_DIR / "cv_embeddings.csv")
    (jd_df, jd_embeddings), _ = load_embeddings(EMBEDDINGS_DIR / "jd_embeddings.csv")
    print(f"Loaded {len(cv_df)} CVs and {len(jd_df)} JDs")
    
    # Validate
    validate_embeddings(cv_df, jd_df)
    
    # Execute matching
    print(f"Matching with TOP_K={TOP_K}...")
    results = match_all_jds(jd_df, jd_embeddings, cv_df, cv_embeddings)
    
    # Save outputs
    json_path = save_results(results, OUTPUT_DIR)
    
    # Prepare reranker data
    reranker_df = prepare_reranker_data(results, cv_df, jd_df)
    reranker_path = OUTPUT_DIR / "reranker_input.csv"
    reranker_df.to_csv(reranker_path, index=False)
    
    # Summary stats
    quality_counts = {'excellent': 0, 'good': 0, 'weak': 0}
    for info in results.values():
        quality_counts[info['quality']] += 1
    
    sla_passed, p95 = latency_tracker.check_sla()
    
    print(f"\nResults:")
    print(f"  Processed: {len(jd_df)} JDs x {len(cv_df)} CVs")
    print(f"  Quality: EXC={quality_counts['excellent']}, GOOD={quality_counts['good']}, WEAK={quality_counts['weak']}")
    print(f"  Latency p95: {p95:.1f}ms ({'PASS' if sla_passed else 'FAIL'})")
    print(f"  Output: {OUTPUT_DIR}/")


if __name__ == "__main__":
    main()
