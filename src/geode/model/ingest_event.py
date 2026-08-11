from sqlalchemy import (
    Column, Integer, String, BigInteger, DateTime, UniqueConstraint, ForeignKey
)

from .base import Base


class IngestEvent(Base):
    __tablename__ = "ingest_events"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)
    ingest_time = Column(DateTime, nullable=False)

    def __repr__(self):
        return (
            f"<IngestEvent(id={self.id}, "
            f"file_id={self.file_id}, "
            f"ingest_time={self.ingest_time})>"
        )
