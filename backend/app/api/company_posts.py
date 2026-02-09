from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from ..auth import get_db, get_current_user
from ..models.company_post import CompanyPost
from ..models.user import User
from ..schemas.company_post import CompanyPostCreate, CompanyPostUpdate, CompanyPostOut

router = APIRouter(prefix="/company-posts", tags=["company-posts"])

@router.get("/", response_model=list[CompanyPostOut])
def list_company_posts(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    q = db.query(CompanyPost).filter(CompanyPost.company_id == current_user.id)
    return q.order_by(CompanyPost.created_at.desc()).all()

@router.post("/", response_model=CompanyPostOut, status_code=status.HTTP_201_CREATED)
def create_company_post(
    payload: CompanyPostCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = CompanyPost(
        company_id=current_user.id,
        text=payload.text,
        images=payload.images or [],
    )
    db.add(post)
    db.commit()
    db.refresh(post)
    return post

@router.put("/{post_id}", response_model=CompanyPostOut)
def update_company_post(
    post_id: str,
    payload: CompanyPostUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(CompanyPost).filter(
        CompanyPost.id == post_id,
        CompanyPost.company_id == current_user.id,
    ).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post non trovato")
    post.text = payload.text
    post.images = payload.images or []
    db.commit()
    db.refresh(post)
    return post

@router.delete("/{post_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_company_post(
    post_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    post = db.query(CompanyPost).filter(
        CompanyPost.id == post_id,
        CompanyPost.company_id == current_user.id,
    ).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post non trovato")
    db.delete(post)
    db.commit()
