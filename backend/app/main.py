import os
from .api.parse import router as parse_router
from .api.embeddings import router as embeddings_router
from .api.jd import router as jd_router
from .api.cv_versioning import router as cv_versioning_router
from .database import get_db
from fastapi import Depends, FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg2 import Psycopg2Instrumentor
from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
from .core.metrics import meter, tracer
from .core.service_endpoints import router as service_router
from sqlalchemy import text
from sqlalchemy.orm import Session


app = FastAPI(title="PiazzaTi Backend", version="1.0.0")
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# Register parsing API router (PDF -> parsed JSON)
app.include_router(parse_router, prefix="/api")

# Register embeddings API router (CSV processing & similarity search)
app.include_router(embeddings_router, prefix="/api")

app.include_router(jd_router, prefix="/api")
# Register CV versioning API router
app.include_router(cv_versioning_router, prefix="/api")

# Instrument FastAPI automatically (per tracciare le richieste)
FastAPIInstrumentor.instrument_app(app)
SQLAlchemyInstrumentor().instrument()
Psycopg2Instrumentor().instrument()

# Register service endpoints router
app.include_router(service_router)

# metriche personalizzate:


@app.get("/")
async def root():
    return {"message": "Benvenuto su PiazzaTi!"}


