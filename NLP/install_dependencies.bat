@echo off
REM ============================================================================
REM install_dependencies.bat
REM Script per installare le dipendenze necessarie su Windows
REM ============================================================================
echo.
echo ============================================================================
echo INSTALLAZIONE DIPENDENZE
echo ============================================================================
echo.

REM Verifica Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [ERRORE] Python non trovato
    echo Scarica Python da: https://www.python.org/downloads/
    pause
    exit /b 1
)
echo [OK] Python installato
python --version
echo.

REM Verifica pip
python -m pip --version >nul 2>&1
if errorlevel 1 (
    echo [WARNING] pip non trovato. Installazione in corso...
    python -m ensurepip --default-pip
)
echo [OK] pip disponibile
echo.

REM Aggiorna pip
echo [INFO] Aggiornamento pip...
python -m pip install --upgrade pip --quiet
echo [OK] pip aggiornato
echo.

REM ============================================================================
REM DIPENDENZE BASE - JSON to CSV Processors
REM ============================================================================
echo [INFO] Installazione dipendenze base...
echo.

REM Installa pandas
echo [INFO] Installazione pandas...
python -m pip install pandas --quiet
if errorlevel 1 (
    echo [ERRORE] Impossibile installare pandas
    pause
    exit /b 1
)
echo [OK] pandas installato
echo.

REM Installa python-dateutil (per normalizzatore)
echo [INFO] Installazione python-dateutil...
python -m pip install python-dateutil --quiet
if errorlevel 1 (
    echo [ERRORE] Impossibile installare python-dateutil
    pause
    exit /b 1
)
echo [OK] python-dateutil installato
echo.

REM ============================================================================
REM DIPENDENZE EMBEDDING GENERATOR
REM ============================================================================
echo [INFO] Installazione dipendenze per Embedding Generator...
echo.

REM Installa numpy
echo [INFO] Installazione numpy...
python -m pip install numpy --quiet
if errorlevel 1 (
    echo [ERRORE] Impossibile installare numpy
    pause
    exit /b 1
)
echo [OK] numpy installato
echo.

REM Installa PyTorch (CPU version per compatibilità)
echo [INFO] Installazione PyTorch (CPU version)...
echo [WARNING] Questo potrebbe richiedere alcuni minuti...
python -m pip install torch --index-url https://download.pytorch.org/whl/cpu --quiet
if errorlevel 1 (
    echo [ERRORE] Impossibile installare PyTorch
    pause
    exit /b 1
)
echo [OK] PyTorch installato
echo.

REM Installa sentence-transformers
echo [INFO] Installazione sentence-transformers...
echo [WARNING] Questo potrebbe richiedere alcuni minuti...
python -m pip install sentence-transformers --quiet
if errorlevel 1 (
    echo [ERRORE] Impossibile installare sentence-transformers
    pause
    exit /b 1
)
echo [OK] sentence-transformers installato
echo.

REM Installa pyjwt
echo [INFO] Installazione pyjwt...
python -m pip install pyjwt --quiet
if errorlevel 1 (
    echo [ERRORE] Impossibile installare pyjwt
    pause
    exit /b 1
)
echo [OK] pyjwt installato
echo.

REM ============================================================================
REM VERIFICA INSTALLAZIONE
REM ============================================================================
echo [INFO] Verifica dipendenze installate...
echo.

echo [TEST] Dipendenze base...
python -c "import pandas as pd; print('[OK] pandas versione:', pd.__version__)"
if errorlevel 1 goto error_pandas

python -c "from dateutil import parser; print('[OK] python-dateutil disponibile')"
if errorlevel 1 goto error_dateutil

python -c "import json; print('[OK] json disponibile')"
python -c "from pathlib import Path; print('[OK] pathlib disponibile')"
python -c "from typing import List, Dict, Set, Tuple; print('[OK] typing disponibile')"
python -c "from datetime import datetime; print('[OK] datetime disponibile')"
python -c "import re; print('[OK] re disponibile')"
python -c "from collections import defaultdict; print('[OK] collections disponibile')"
echo.

echo [TEST] Dipendenze embedding generator...
python -c "import numpy as np; print('[OK] numpy versione:', np.__version__)"
if errorlevel 1 goto error_numpy

python -c "import torch; print('[OK] PyTorch versione:', torch.__version__)"
if errorlevel 1 goto error_torch

python -c "from sentence_transformers import SentenceTransformer; print('[OK] sentence-transformers disponibile')"
if errorlevel 1 goto error_sentence_transformers

echo.

REM ============================================================================
REM TEST MODELLO SBERT
REM ============================================================================
echo [INFO] Test caricamento modello SBERT...
python -c "from sentence_transformers import SentenceTransformer; model = SentenceTransformer('sentence-transformers/paraphrase-multilingual-MiniLM-L12-v2'); print('[OK] Modello SBERT caricato con successo')"
if errorlevel 1 (
    echo [WARNING] Primo caricamento del modello potrebbe richiedere tempo per il download
    echo [WARNING] Il modello verrà scaricato automaticamente alla prima esecuzione di embed_generator.py
)
echo.

REM ============================================================================
REM SUCCESS
REM ============================================================================
echo ============================================================================
echo [SUCCESS] Installazione completata con successo
echo ============================================================================
echo.
echo Dipendenze installate:
echo.
echo   BASE (JSON to CSV):
echo     - pandas (CSV processing)
echo     - python-dateutil (date parsing)
echo     - json, pathlib, typing, datetime, re, collections (built-in)
echo.
echo   EMBEDDING GENERATOR:
echo     - numpy (array operations)
echo     - torch (PyTorch - ML framework)
echo     - sentence-transformers (SBERT models)
echo.
echo Script disponibili:
echo   1. python cv_json_to_dataset_processor.py
echo   2. python jd_json_to_dataset_processor.py
echo   3. python normalize_dataset.py
echo   4. python embed_generator.py
echo.
echo NOTA: Il primo avvio di embed_generator.py scaricherà il modello SBERT
echo       (~500MB). Assicurati di avere connessione internet.
echo.
pause
exit /b 0

REM ============================================================================
REM ERROR HANDLERS
REM ============================================================================
:error_pandas
echo [ERRORE] Verifica pandas fallita
pause
exit /b 1

:error_dateutil
echo [ERRORE] Verifica python-dateutil fallita
pause
exit /b 1

:error_numpy
echo [ERRORE] Verifica numpy fallita
pause
exit /b 1

:error_torch
echo [ERRORE] Verifica PyTorch fallita
pause
exit /b 1

:error_sentence_transformers
echo [ERRORE] Verifica sentence-transformers fallita
pause
exit /b 1
