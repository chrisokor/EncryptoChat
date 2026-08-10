from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy import Column, String, Integer, DateTime, Boolean, ForeignKey
from sqlalchemy.sql import func
from datetime import datetime


Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    username = Column(String, primary_key=True, index=False)
    public_key = Column(String, nullable=False)
    signing_public_key = Column(String, nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Prekey(Base):
    __tablename__ = "prekeys"

    id = Column(String, primary_key=True)
    username = Column(String, ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    key = Column(String, nullable=False)
    used = Column(Boolean, default=False, nullable=False)
    used_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Message(Base):
    __tablename__ = "messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    to_user = Column(String, ForeignKey("users.username", ondelete="CASCADE"), nullable=False, index=True)
    from_user = Column(String, nullable=False)
    ciphertext = Column(String, nullable=False)
    prekey_id = Column(String, nullable=True) # track which prekey was used
    status = Column(String, default="queued", nullable=False)
    delivered_at = Column(DateTime(timezone=True), nullable=True)
    read_at = Column(DateTime(timezone=True), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
