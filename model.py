from sqlalchemy import Column, String, Integer, Boolean, Date
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