from sqlalchemy import Column, String, Integer, Boolean, Date, DateTime
from sqlalchemy.sql import func
from db import Base

class License(Base):
    __tablename__ = "licenses"

    license_key = Column(String, primary_key=True, index=True)
    hwid = Column(String, nullable=True)

    plan = Column(String)  # demo, weekly, monthly, yearly
    expires_at = Column(Date, nullable=True)

    usage_count = Column(Integer, default=0)
    usage_limit = Column(Integer, default=5)

    active = Column(Boolean, default=True)
    notes  = Column(String, nullable=True)
    created_at = Column(DateTime, server_default=func.now())


class UsageLog(Base):
    __tablename__ = "usage_logs"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    license_key = Column(String, index=True)
    plan        = Column(String, nullable=True)
    event       = Column(String)   # demo_claim | verify | process_image
    notes       = Column(String, nullable=True)  # phone (demo), hwid (verify/process)
    created_at  = Column(DateTime, server_default=func.now())
