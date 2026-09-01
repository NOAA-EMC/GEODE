from sqlalchemy import (
    Column, Integer, String, BigInteger, DateTime, UniqueConstraint, ForeignKey
)

from .base import Base


class QueryEvent(Base):
    __tablename__ = "query_events"

    id = Column(Integer, primary_key=True)
    file_id = Column(Integer, ForeignKey("files.id"), nullable=False)

    def __repr__(self):
        return (
            f"<QueryEvent(id={self.id}, "
            f"file_id={self.file_id})>"
        )
