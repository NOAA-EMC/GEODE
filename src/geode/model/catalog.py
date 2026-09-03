from sqlalchemy import Column, Integer, String

from .base import Base


class Catalog(Base):
    __tablename__ = "catalogs"

    id = Column(Integer, primary_key=True)
    name = Column(String, nullable=False, unique=True, index=True, default="root")
    root_path = Column(String, nullable=False, unique=True, index=True)

    def __repr__(self):
        return (
            f"<Catalog(id={self.id}, "
            f"name='{self.name}', "
            f"root_path='{self.root_path}')>"
        )
