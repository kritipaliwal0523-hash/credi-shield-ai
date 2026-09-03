from datetime import date, datetime

from sqlalchemy import Column, Integer, String, Date, Float, ForeignKey
from sqlalchemy.orm import relationship

from .database import Base


class Buyer(Base):
    __tablename__ = "buyers"

    id = Column(Integer, primary_key=True, index=True)
    buyer_name = Column(String, unique=True, index=True, nullable=False)
    industry = Column(String, nullable=True)
    country = Column(String, nullable=True)

    transactions = relationship("Transaction", back_populates="buyer")
    reliability_score = relationship(
        "ReliabilityScore", uselist=False, back_populates="buyer"
    )


class Transaction(Base):
    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True, index=True)
    invoice_id = Column(String, unique=True, index=True, nullable=False)
    buyer_id = Column(Integer, ForeignKey("buyers.id"), nullable=False)
    invoice_amount = Column(Float, nullable=False)
    issue_date = Column(Date, nullable=False)
    due_date = Column(Date, nullable=False)
    payment_date = Column(Date, nullable=True)

    buyer = relationship("Buyer", back_populates="transactions")

    @property
    def payment_delay(self) -> int | None:
        if self.payment_date is None:
            return None
        return (self.payment_date - self.due_date).days


class ReliabilityScore(Base):
    __tablename__ = "reliability_scores"

    id = Column(Integer, primary_key=True, index=True)
    buyer_id = Column(Integer, ForeignKey("buyers.id"), unique=True)
    average_delay = Column(Float, nullable=False)
    late_payment_percentage = Column(Float, nullable=False)
    reliability_score = Column(Float, nullable=False)
    predicted_delay_probability = Column(Float, nullable=True)
    risk_classification = Column(String, nullable=False)
    recommendation = Column(String, nullable=True)
    updated_at = Column(Date, default=datetime.utcnow)

    buyer = relationship("Buyer", back_populates="reliability_score")

