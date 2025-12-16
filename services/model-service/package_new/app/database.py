"""
Database models and utilities for Model Service.
"""
import os
from datetime import datetime
from typing import Optional, List, Dict, Any

from sqlalchemy import create_engine, Column, String, Float, Boolean, DateTime, JSON, Integer
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession

Base = declarative_base()


class ModelVersion(Base):
    """Model version table."""

    __tablename__ = "model_versions"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(String(50), default="active")
    model_type = Column(String(100))
    model_path = Column(String(500))
    s3_path = Column(String(500))
    metrics = Column(JSON)
    training_job_id = Column(String(100))
    is_production = Column(Boolean, default=False)
    description = Column(String(1000))
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TrainingJob(Base):
    """Training job table."""

    __tablename__ = "training_jobs"

    id = Column(Integer, primary_key=True, autoincrement=True)
    job_id = Column(String(100), unique=True, nullable=False, index=True)
    status = Column(String(50), default="queued")
    config = Column(JSON)
    include_feedback = Column(Boolean, default=False)
    description = Column(String(1000))
    progress = Column(Float, default=0.0)
    current_epoch = Column(Integer)
    total_epochs = Column(Integer)
    metrics = Column(JSON)
    error_message = Column(String(2000))
    model_version = Column(String(100))
    started_at = Column(DateTime)
    completed_at = Column(DateTime)
    created_at = Column(DateTime, default=datetime.utcnow)


class Database:
    """Database connection manager."""

    def __init__(self, database_url: str):
        self.database_url = database_url
        self.engine = None
        self.session_factory = None

    async def initialize(self):
        """Initialize database connection."""
        # For synchronous operations with psycopg2
        sync_url = self.database_url.replace("postgresql+asyncpg://", "postgresql://")
        self.engine = create_engine(sync_url)
        self.session_factory = sessionmaker(bind=self.engine)

        # Create tables
        Base.metadata.create_all(self.engine)

    async def close(self):
        """Close database connection."""
        if self.engine:
            self.engine.dispose()

    def get_session(self):
        """Get database session."""
        return self.session_factory()

    async def create_model_version(
        self,
        version: str,
        model_type: str,
        model_path: str,
        metrics: Dict[str, Any],
        training_job_id: str,
        s3_path: Optional[str] = None,
        description: Optional[str] = None
    ) -> ModelVersion:
        """Create a new model version."""
        with self.get_session() as session:
            model_version = ModelVersion(
                version=version,
                model_type=model_type,
                model_path=model_path,
                s3_path=s3_path,
                metrics=metrics,
                training_job_id=training_job_id,
                description=description
            )
            session.add(model_version)
            session.commit()
            session.refresh(model_version)
            return model_version

    async def get_model_version(self, version: str) -> Optional[ModelVersion]:
        """Get model version by version string."""
        with self.get_session() as session:
            return session.query(ModelVersion).filter(
                ModelVersion.version == version
            ).first()

    async def get_production_model(self) -> Optional[ModelVersion]:
        """Get the production model."""
        with self.get_session() as session:
            return session.query(ModelVersion).filter(
                ModelVersion.is_production == True
            ).first()

    async def list_model_versions(
        self,
        limit: int = 10,
        offset: int = 0,
        status: Optional[str] = None
    ) -> List[ModelVersion]:
        """List model versions."""
        with self.get_session() as session:
            query = session.query(ModelVersion)
            if status:
                query = query.filter(ModelVersion.status == status)
            return query.order_by(ModelVersion.created_at.desc()).offset(offset).limit(limit).all()

    async def set_production_model(self, version: str) -> bool:
        """Set a model version as production."""
        with self.get_session() as session:
            # Unset current production model
            session.query(ModelVersion).filter(
                ModelVersion.is_production == True
            ).update({"is_production": False})

            # Set new production model
            result = session.query(ModelVersion).filter(
                ModelVersion.version == version
            ).update({"is_production": True})

            session.commit()
            return result > 0

    async def create_training_job(
        self,
        job_id: str,
        config: Dict[str, Any],
        include_feedback: bool,
        description: Optional[str] = None
    ) -> TrainingJob:
        """Create a new training job."""
        with self.get_session() as session:
            job = TrainingJob(
                job_id=job_id,
                config=config,
                include_feedback=include_feedback,
                description=description
            )
            session.add(job)
            session.commit()
            session.refresh(job)
            return job

    async def update_training_job(
        self,
        job_id: str,
        **kwargs
    ) -> bool:
        """Update training job."""
        with self.get_session() as session:
            result = session.query(TrainingJob).filter(
                TrainingJob.job_id == job_id
            ).update(kwargs)
            session.commit()
            return result > 0

    async def get_training_job(self, job_id: str) -> Optional[TrainingJob]:
        """Get training job by ID."""
        with self.get_session() as session:
            return session.query(TrainingJob).filter(
                TrainingJob.job_id == job_id
            ).first()
