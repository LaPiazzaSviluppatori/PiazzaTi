"""
Servizio per gestire il salvataggio dei JSON parsati per il batch processing NLP.
Organizza i CV in cartelle per data e user_id per facilitare il processing periodico.
"""

import json
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, Optional
import hashlib
import uuid

from ..schemas.parsed_document import ParsedDocument


class CVBatchStorage:
    """
    Gestisce il salvataggio dei CV parsati per il batch processing NLP.
    Organizza i file per data e utente per facilitare il processing periodico.
    """
    
    def __init__(self):
        # Path base per i JSON del modulo NLP **dentro il container backend**.
        # Questa cartella è montata come volume in docker-compose:
        #   /var/lib/docker/piazzati-data:/app/NLP/data
        # In questo modo:
        #   - il backend salva i CV in /app/NLP/data/cvs
        #   - la pipeline NLP (cv_json_to_dataset_processor.py) legge dalla stessa cartella
        self.base_path = Path("/app/NLP/data/cvs")
        self.base_path.mkdir(parents=True, exist_ok=True)
        print(f"📁 CVBatchStorage inizializzato: {self.base_path}")
    
    def save_parsed_cv(self, doc: ParsedDocument, original_filename: Optional[str] = None) -> str:
        """
        Salva un CV parsato come JSON per il batch processing.
        
        Args:
            doc: Documento parsato dal parser
            original_filename: Nome file originale (opzionale)
            
        Returns:
            str: Path del file JSON salvato
        """
        try:
            # Genera metadata per il file
            file_info = self._generate_file_info(doc, original_filename)
            
            # Salva direttamente nella cartella base
            json_path = self.base_path / file_info["filename"]
            
            # Prepara i dati per il salvataggio
            cv_data = self._prepare_cv_data(doc, file_info)
            
            # Salva il JSON
            with open(json_path, 'w', encoding='utf-8') as f:
                json.dump(cv_data, f, indent=2, ensure_ascii=False, default=str)
            
            print(f"💾 CV salvato per batch processing: {json_path.name}")
            print(f"   User: {cv_data.get('user_id', 'N/A')} | Skills: {len(cv_data.get('skills', []))}")
            
            return str(json_path)
            
        except Exception as e:
            print(f"❌ Errore salvataggio CV batch: {e}")
            return ""
    
    def _generate_file_info(self, doc: ParsedDocument, original_filename: Optional[str]) -> Dict[str, Any]:
        """Genera informazioni per il file JSON."""
        
        # Usa document_id se disponibile, altrimenti genera uno
        doc_id = getattr(doc, 'document_id', None) or str(uuid.uuid4())
        
        # User ID per organizzazione
        user_id = getattr(doc, 'user_id', None) or 'unknown'
        
        # Timestamp
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        
        # Nome file pulito
        safe_filename = self._sanitize_filename(original_filename) if original_filename else "cv"
        
        # Nome file finale: user_id_timestamp_filename.json
        filename = f"{user_id}_{timestamp}_{safe_filename}_{doc_id[:8]}.json"
        
        return {
            "filename": filename,
            "document_id": doc_id,
            "user_id": user_id,
            "timestamp": timestamp,
            "original_filename": original_filename
        }
    
    # Rimossa logica sottocartelle per data
    
    def _sanitize_filename(self, filename: str) -> str:
        """Pulisce il nome file rimuovendo caratteri non sicuri."""
        if not filename:
            return "cv"
            
        # Rimuovi estensione
        name = Path(filename).stem
        
        # Sostituisci caratteri non sicuri
        safe_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-"
        cleaned = ''.join(c if c in safe_chars else '_' for c in name)
        
        # Limita lunghezza
        return cleaned[:50] if cleaned else "cv"
    
    def _prepare_cv_data(self, doc: ParsedDocument, file_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Prepara i dati del CV per il salvataggio in formato compatibile con il modulo NLP.
        """
        
        # Converti il documento in dizionario
        if hasattr(doc, 'model_dump'):
            cv_data = doc.model_dump()
        elif hasattr(doc, 'dict'):
            cv_data = doc.dict()
        else:
            cv_data = doc.__dict__.copy()
        
        # Aggiungi metadati per batch processing
        cv_data.update({
            # Metadati file
            "batch_metadata": {
                "saved_at": datetime.now().isoformat(),
                "original_filename": file_info["original_filename"],
                "processing_version": "1.0",
                "ready_for_batch": True
            }
        })
        
        # Assicurati che ci siano gli ID necessari
        if 'document_id' not in cv_data or not cv_data['document_id']:
            cv_data['document_id'] = file_info["document_id"]
            
        if 'user_id' not in cv_data or not cv_data['user_id']:
            cv_data['user_id'] = file_info["user_id"]
        
        return cv_data
    
    def get_batch_stats(self) -> Dict[str, Any]:
        """Ottieni statistiche sui CV salvati per batch processing (senza sottocartelle per data)."""
        stats = {
            "total_files": 0,
            "files_by_user": {},
            "latest_files": [],
            "processing_ready": 0
        }
        try:
            json_files = list(self.base_path.glob("*.json"))
            stats["total_files"] = len(json_files)
            for json_file in json_files[-10:]:  # Ultimi 10 file
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                    user_id = data.get('user_id', 'unknown')
                    stats["files_by_user"][user_id] = stats["files_by_user"].get(user_id, 0) + 1
                    if data.get('batch_metadata', {}).get('ready_for_batch', False):
                        stats["processing_ready"] += 1
                    stats["latest_files"].append({
                        "filename": json_file.name,
                        "user_id": user_id,
                        "skills_count": len(data.get('skills', []))
                    })
                except Exception:
                    continue
        except Exception as e:
            print(f"❌ Errore calcolo statistiche batch: {e}")
        return stats
    
    def cleanup_old_files(self, days_to_keep: int = 30) -> int:
        """
        Pulisce file JSON più vecchi di N giorni nella cartella base.
        Restituisce il numero di file rimossi.
        """
        removed_count = 0
        cutoff_date = datetime.now() - timedelta(days=days_to_keep)
        try:
            for json_file in self.base_path.glob("*.json"):
                try:
                    file_mtime = datetime.fromtimestamp(json_file.stat().st_mtime)
                    if file_mtime < cutoff_date:
                        json_file.unlink()
                        removed_count += 1
                        print(f"🗑️ Rimossa file obsoleto: {json_file.name}")
                except Exception:
                    continue
        except Exception as e:
            print(f"❌ Errore cleanup file: {e}")
        return removed_count


# Singleton instance
_batch_storage: Optional[CVBatchStorage] = None

def get_batch_storage() -> CVBatchStorage:
    """Ottieni istanza singleton del batch storage."""
    global _batch_storage
    if _batch_storage is None:
        _batch_storage = CVBatchStorage()
    return _batch_storage