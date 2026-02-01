# PiazzaTi – Documentazione Funzionale e Tecnica

PiazzaTi è una piattaforma web per la gestione, presentazione e matching tra candidati e offerte di lavoro (job description, JD). Supporta due ruoli principali: **Candidato** e **Azienda**.

---

## Flusso Utente

### Candidato
1. **Registrazione/Login**: Accesso tramite email/password, scelta ruolo.
2. **Gestione Profilo**: Modifica dati personali, competenze (skills), esperienze, progetti, post.
3. **Upload CV**: Caricamento CV (PDF/testo), parsing automatico e aggiornamento profilo.
4. **Tag Opt-in**: Aggiunta di tag personali (es. diversity, background).
5. **Scopri**: Visualizza JD con match elevato rispetto alle proprie competenze (match ≥ 60%).
6. **Connessioni**: Può connettersi con altri candidati suggeriti.

### Azienda
1. **Registrazione/Login**: Accesso tramite email/password, scelta ruolo.
2. **Gestione JD**: Crea, visualizza e modifica offerte di lavoro.
3. **Shortlist**: Visualizza i candidati più compatibili per ogni JD (ordinati per punteggio match).
4. **Pipeline**: Gestione avanzata del processo di selezione (screening, feedback, audit).
5. **Audit Log**: Tracciamento delle azioni rilevanti per compliance.

---

## Composizione Tecnica
- **Frontend**: React + TypeScript, struttura a componenti modulari (CandidateSection, CompanySection, DiscoverSection, PipelineSection, ecc.).
- **Backend**: Python (FastAPI), gestione autenticazione JWT, parsing CV, API RESTful.
- **Database**: PostgreSQL (gestione dati utenti, JD, connessioni, log, feedback).
- **Altre tecnologie**: Docker, Nginx, monitoring (Prometheus, Grafana), Makefile per automazione, script di deploy.

---

## Chiamate Principali (API)
- `POST /auth/register` – Registrazione utente (email, password, nome, ruolo). Password hashata e validazione email.
- `POST /auth/token` – Login utente (JWT).
- `POST /api/parse/upload` – Upload e parsing CV (risposta immediata o asincrona con polling).
- `GET /api/parse/task/{task_id}` – Stato parsing CV (se asincrono).
- `GET/POST /api/jd` – Gestione job description.
- `GET/POST /api/candidate` – Gestione profilo candidato.
- `GET/POST /api/connection` – Gestione connessioni tra utenti.
- `GET/POST /api/feedback` – Feedback su candidati/JD.
- (Altre API per pipeline, audit log, ecc.)

---

## Logica di Matching
- Il matching tra candidato e JD si basa su:
  - Competenze richieste (must/nice to have)
  - Percentuale di match: 70% must-have, 30% nice-to-have
  - Solo JD con match ≥ 60% vengono suggerite nella sezione "Scopri"
- La shortlist aziendale mostra i candidati ordinati per punteggio di compatibilità.

---

## Pipeline del Processo
- **Candidato**: CV Ingest → Screening → Feedback → Audit
- **Azienda**: JD Creation → Screening → Feedback → Audit
- Ogni fase è rappresentata graficamente nella sezione Pipeline.

---

## Ruoli Utente
- **Candidato**: Gestisce il proprio profilo, vede JD consigliate, si connette con altri candidati.
- **Azienda**: Crea JD, vede shortlist di candidati, gestisce pipeline di selezione.

---

## Note Tecniche e Sicurezza
- Autenticazione JWT, gestione ruoli lato frontend e backend.
- Registrazione sicura: password hashata, validazione email tramite email-validator (Pydantic).
- Parsing CV robusto, con polling asincrono e feedback di avanzamento.
- Audit log per tracciamento azioni sensibili.
- Modalità DEI (Diversity, Equity, Inclusion) opzionale per aziende.
- Tutte le azioni principali sono tracciate e persistite.

---

Per dettagli tecnici o estensioni, consultare la documentazione completa nei file README.md del progetto.