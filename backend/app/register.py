from fastapi import APIRouter, Depends, HTTPException, status, Form
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
import uuid

from .database import get_db
from .models.user import User
from .auth import get_password_hash, get_user_by_email

router = APIRouter()

class UserCreate(BaseModel):
    email: EmailStr
    password: str
    # Campi comuni
    name: str | None = None
    surname: str | None = None
    city: str | None = None
    region: str | None = None
    country: str | None = None
    # Campi azienda
    companyName: str | None = None
    # Ruolo
    role: str = "candidate"  # default role


@router.post("/auth/register", status_code=201)
def register_user(
    user: UserCreate,
    db: Session = Depends(get_db),
):
    # Check if user already exists
    if get_user_by_email(db, user.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    hashed_password = get_password_hash(user.password)
    # Costruzione nome completo per azienda o candidato
    if user.role == "company":
        name = user.name or ""
        surname = user.surname or ""
        company = user.companyName or ""
    else:
        name = user.name or ""
        surname = user.surname or ""
        company = None
    db_user = User(
        id=uuid.uuid4(),
        email=user.email,
        name=name,
        password_hash=hashed_password,
        role=user.role,
        is_active=True,
        company=company,
        # Salva anche altri campi se presenti nel modello User
        # city, region, country, surname
        # NB: aggiungi questi campi al modello User se non ci sono
        city=user.city,
        region=user.region,
        country=user.country,
        surname=surname,
    )
    db.add(db_user)
    db.commit()
    db.refresh(db_user)
    return {"id": str(db_user.id), "email": db_user.email, "role": db_user.role}
