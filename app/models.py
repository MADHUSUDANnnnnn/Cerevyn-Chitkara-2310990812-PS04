"""
models.py - SQLAlchemy ORM models for persisting support tickets and states.
"""

from datetime import datetime
from sqlalchemy import Column, DateTime, Float, Integer, String, Text
from app.db import Base


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String(64), unique=True, index=True, nullable=False)
    message = Column(Text, nullable=False)
    category = Column(String(32), nullable=False)
    priority = Column(String(16), nullable=False)
    assigned_team = Column(String(64), nullable=False)
    summary = Column(Text, nullable=False)
    draft_response = Column(Text, nullable=False)
    status = Column(String(32), nullable=False, default="received")
    confidence = Column(Float, nullable=False)
    draft_source = Column(String(16), nullable=False, default="template")
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow, nullable=False)

    def to_dict(self):
        return {
            "ticket_id": self.ticket_id,
            "message": self.message,
            "category": self.category,
            "priority": self.priority,
            "assigned_team": self.assigned_team,
            "summary": self.summary,
            "draft_response": self.draft_response,
            "status": self.status,
            "confidence": self.confidence,
            "draft_source": self.draft_source,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
