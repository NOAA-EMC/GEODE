from sqlalchemy import (
    Column, Integer, String, BigInteger, DateTime, UniqueConstraint, ForeignKey
)

from .base import Base


class DataSet(Base):
    __tablename__ = "data_sets"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True, index=True)

    def __repr__(self):
        return (
            f"<DataSet(id={self.id}, "
            f"name='{self.name}')>"
        )

