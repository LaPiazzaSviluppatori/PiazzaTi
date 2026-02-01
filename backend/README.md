# PiazzaTi Backend – Aggiornamento 2026

## Novità

- **Nuovo endpoint di registrazione**: `POST /auth/register` per creare utenti (email, password, nome, ruolo). Le password sono hashate e la validazione email è automatica tramite Pydantic.
- **Nuova dipendenza**: aggiunto `email-validator` a requirements.txt (necessario per la validazione email di Pydantic).

## Esempio richiesta registrazione

```json
POST /auth/register
{
	"email": "test@example.com",
	"password": "password123",
	"name": "Mario Rossi",
	"role": "admin"
}
```

Risposta:
```json
{
	"id": "...",
	"email": "test@example.com",
	"role": "admin"
}
```

## Dipendenze aggiuntive

- email-validator (obbligatorio per la registrazione)

## Note operative

Dopo ogni modifica a requirements.txt, ricostruire l’immagine Docker del backend:

```
docker-compose build backend
docker-compose restart backend
```
