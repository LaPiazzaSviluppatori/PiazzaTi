from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class CompanyPostBase(BaseModel):
    text: str
    images: Optional[List[str]] = None

class CompanyPostCreate(CompanyPostBase):
    pass

class CompanyPostUpdate(CompanyPostBase):
    pass

class CompanyPostOut(CompanyPostBase):
    id: str
    created_at: datetime

    class Config:
        from_attributes = True
