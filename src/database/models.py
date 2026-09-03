from datetime import datetime, timezone
import uuid
from sqlalchemy import String, Integer, DateTime, ForeignKey, JSON, Text
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

# 1. Base Class
# All SQLAlchemy models must inherit from a DeclarativeBase class.
# This serves as the central registry for all database models/tables.
class Base(DeclarativeBase):
    pass 


# 2. Repository Table
# Stores metadata for each GitHub repository submitted for analysis.
class Repository(Base):
    __tablename__ = "repositories"

    # Primary Key: UUID generated automatically as a string (e.g. "550e8400-e29b-...")
    id: Mapped[str] = mapped_column(
        String, 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )
    
    # Target GitHub URL (Must be unique across the system)
    url: Mapped[str] = mapped_column(String, unique=True, nullable=False)

    # Repository name (e.g. "django") - populated after clone/analysis
    name: Mapped[str | None] = mapped_column(String, nullable=True)

    # Ingestion status: 'pending', 'processing', 'completed', or 'failed'
    status: Mapped[str] = mapped_column(String, default="pending", nullable=False)

    # Total file count - populated after analysis
    file_count: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Default branch name (e.g. "main" or "master")
    default_branch: Mapped[str | None] = mapped_column(String, nullable=True)

    # Local folder path where repo was cloned (e.g. "data/repos/<id>")
    clone_path: Mapped[str | None] = mapped_column(String, nullable=True)

    # Timestamps (Stored in UTC timezone)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False, 
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False, 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )

    files: Mapped[list["File"]] = relationship(back_populates="repository", cascade="all, delete-orphan")


# 3. Job Table
# Tracks background tasks responsible for cloning & ingesting repositories.
class Job(Base):
    __tablename__ = "jobs"  # Lowercase plural convention

    # Primary Key: UUID string for identifying this specific background task
    id: Mapped[str] = mapped_column(
        String, 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )

    # Foreign Key: Links this job directly to a record in the 'repositories' table
    repository_id: Mapped[str] = mapped_column(
        String, 
        ForeignKey("repositories.id"), 
        nullable=False
    )

    # Job status: 'queued', 'processing', 'completed', or 'failed'
    status: Mapped[str] = mapped_column(String, default="queued", nullable=False)

    # Progress percentage from 0 to 100
    progress: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # Stores an error message if the job fails
    error: Mapped[str | None] = mapped_column(String, nullable=True)

    # Timestamps (Stored in UTC timezone)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False, 
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        nullable=False, 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )

class File(Base):
    __tablename__ = "files"
    id: Mapped[str] = mapped_column(
        String, 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )
    repository_id: Mapped[str] = mapped_column(
        String, 
        ForeignKey("repositories.id"), 
        nullable=False
    )
    path: Mapped[str] = mapped_column(String, nullable=False)
    file_size: Mapped[int] = mapped_column(Integer, nullable=False)
    line_count: Mapped[int] = mapped_column(Integer, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    # Relationships
    repository: Mapped["Repository"] = relationship(back_populates="files")
    symbols: Mapped[list["Symbol"]] = relationship(back_populates="file", cascade="all, delete-orphan")

class Symbol(Base):
    __tablename__ = "symbols"
    id: Mapped[str] = mapped_column(
        String, 
        primary_key=True, 
        default=lambda: str(uuid.uuid4())
    )
    file_id: Mapped[str] = mapped_column(
        String, 
        ForeignKey("files.id"), 
        nullable=False
    )
    name: Mapped[str] = mapped_column(String, nullable=False)
    symbol_type: Mapped[str] = mapped_column(String, nullable=False)  # 'class', 'function', 'method', 'import'
    parent_class: Mapped[str | None] = mapped_column(String, nullable=True)
    start_line: Mapped[int] = mapped_column(Integer, nullable=False)
    end_line: Mapped[int] = mapped_column(Integer, nullable=False)
    docstring: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_json: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc)
    )
    # Relationship
    file: Mapped["File"] = relationship(back_populates="symbols")