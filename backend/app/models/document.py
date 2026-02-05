from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .user import User
    from .embedding import Embedding
    from .search import SearchResult

import datetime
import uuid
from typing import Optional

from sqlalchemy import (Boolean, CheckConstraint, DateTime, Enum,
                        ForeignKeyConstraint, Index, Integer,
                        PrimaryKeyConstraint, String, Text, Uuid, text)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base


class Document(Base):
    __tablename__ = "documents"
    __table_args__ = (
        CheckConstraint(
            "language::text ~ '^[a-z]{2}$'::text", name="check_language_format"
        ),
        ForeignKeyConstraint(
            ["user_id"], ["users.id"], ondelete="CASCADE", name="documents_user_id_fkey"
        ),
        PrimaryKeyConstraint("id", name="documents_pkey"),
        # RIMOSSO: Index("gin_parsed_json_idx", "parsed_json"),
        Index("idx_jd_open_lang", "language", "created_at"),
        Index("unique_latest_cv_per_user", "user_id", "is_latest", unique=True),
    )

    id: Mapped[uuid.UUID] = mapped_column(Uuid, primary_key=True)
    is_latest: Mapped[bool] = mapped_column(
        Boolean, nullable=False, server_default=text("false")
    )
    user_id: Mapped[Optional[uuid.UUID]] = mapped_column(Uuid)
    type: Mapped[Optional[str]] = mapped_column(Enum("cv", "jd", name="document_type"))
    raw_file_url: Mapped[Optional[str]] = mapped_column(String)
    parsed_json: Mapped[Optional[dict]] = mapped_column(JSONB)
    language: Mapped[Optional[str]] = mapped_column(String(2))
    created_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, server_default=text("now()")
    )
    updated_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime, server_default=text("now()")
    )
    title: Mapped[Optional[str]] = mapped_column(String)
    description_raw: Mapped[Optional[str]] = mapped_column(Text)
    version: Mapped[Optional[int]] = mapped_column(Integer)
    status: Mapped[Optional[str]] = mapped_column(
        Enum(
            "uploaded",
            "parsed",
            "parsing_failed",
            "embedding_failed",
            "draft",
            "open",
            "closed",
            name="document_status",
        )
    )

    # Relationships
    user: Mapped[Optional["User"]] = relationship("User", back_populates="documents")
    embedding: Mapped[Optional["Embedding"]] = relationship(
        "Embedding", uselist=False, back_populates="document"
    )
    search_results: Mapped[list["SearchResult"]] = relationship(
        "SearchResult", back_populates="document"
    )
