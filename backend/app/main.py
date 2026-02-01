import os
from fastapi import Depends, FastAPI, HTTPException, status, Form, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from sqlalchemy.orm import Session
from pydantic import BaseModel

from .auth import authenticate_user, create_access_token, get_db
from .register import router as register_router
from .api.parse import router as parse_router
from .api.embeddings import router as embeddings_router
from .api.jd import router as jd_router
from .api.cv_versioning import router as cv_versioning_router
from .core.metrics import meter, tracer
from .core.service_endpoints import router as service_router

from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

app = FastAPI(title="PiazzaTi Backend", version="1.0.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Endpoint per login: /auth/token
class Token(BaseModel):
    access_token: str
    token_type: str

@app.post("/auth/token", response_model=Token)
def login_for_access_token(
    username: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
):
    user = authenticate_user(db, username, password)
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    access_token = create_access_token(data={"sub": str(user.id)})
    return {"access_token": access_token, "token_type": "bearer"}

# Register routers
app.include_router(parse_router, prefix="/api")
app.include_router(embeddings_router, prefix="/api")
app.include_router(jd_router, prefix="/api")
app.include_router(cv_versioning_router, prefix="/api")
app.include_router(service_router)

# Register the registration endpoint
app.include_router(register_router)

# Instrumentazione OpenTelemetry
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument()
Psycopg2Instrumentor().instrument()

@app.get("/")
async def root():
    return {"message": "Benvenuto su PiazzaTi!"}