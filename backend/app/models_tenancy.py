"""Tenant ORM mapping used by the User.tenant_id foreign key."""

from sqlalchemy import Boolean, Column, Date, DateTime, Integer, String
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func

from app.database import Base


class Tenant(Base):
    __tablename__ = "tenants"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    subdomain = Column(String(100), nullable=False, unique=True, index=True)
    schema_name = Column(String(100), nullable=False, unique=True, index=True)
    plan = Column(String(50), nullable=False, server_default="starter")
    max_users = Column(Integer, nullable=False, server_default="5")
    max_storage_gb = Column(Integer, nullable=False, server_default="10")
    subscription_start = Column(Date, nullable=False)
    subscription_end = Column(Date, nullable=False)
    timezone = Column(String(50), nullable=False, server_default="UTC")
    currency = Column(String(3), nullable=False, server_default="USD")
    locale = Column(String(10), nullable=False, server_default="en_US")
    is_active = Column(Boolean, nullable=False, server_default="true")
    deleted_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    users = relationship("User", foreign_keys="User.tenant_id")
