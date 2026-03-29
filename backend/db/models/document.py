import uuid
from datetime import datetime, timezone
from sqlalchemy import String, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column
from backend.db.postgres import Base


class Document(Base):
    __tablename__ = "documents"
    # Dedup is scoped per user — two users may upload the same file.
    __table_args__ = (
        UniqueConstraint("user_id", "file_hash", name="uq_documents_user_file"),
    )

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), primary_key=True, default=uuid.uuid4
    )
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=True
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    source_path: Mapped[str | None] = mapped_column(String(1000))
    file_hash: Mapped[str | None] = mapped_column(String(64))
    domain: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(String(50), default="processing")
    ingested_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=lambda: datetime.now(timezone.utc))

    def __repr__(self):
        return f"<Document id={self.id} title={self.title}>"
