from sqlalchemy import (
    Column, Integer, String, BigInteger, DateTime, UniqueConstraint, ForeignKey
)

from .base import Base


class File(Base):
    __tablename__ = "files"

    id = Column(Integer, primary_key=True)

    # make foreign key to the catalog table
    catalog_id = Column(Integer, ForeignKey("catalogs.id"), nullable=False)

    # make a forign key that references the data type table
    data_type_id = Column(Integer, ForeignKey("data_types.id"), nullable=False)

    # Absolute canonical path (must be unique)
    path = Column(String, nullable=False, unique=True, index=True)

    # File size in bytes
    size = Column(BigInteger, nullable=False)

    # Last modification time (mtime) of the file
    mtime = Column(DateTime, nullable=False)

    # Start time
    start_time = Column(DateTime, nullable=False)

    # End time
    end_time = Column(DateTime, nullable=False)

    __table_args__ = (
        UniqueConstraint("path", name="uq_files_path"),
    )

    def __repr__(self):
        return (
            f"<File(id={self.id}, "
            f"path='{self.path}', "
            f"size={self.size}, "
            f"mtime={self.mtime}, "
            f"start_time={self.start_time}, "
            f"end_time={self.end_time})>"
        )
