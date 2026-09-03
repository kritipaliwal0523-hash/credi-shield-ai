"""API request/response models (Pydantic).

Kept separate from routes so endpoints stay easy to read and explain.
"""

from __future__ import annotations

from typing import List, Optional

from pydantic import BaseModel, Field


class BuyerSummary(BaseModel):
    buyer_name: str
    average_delay: float
    late_payment_percentage: float
    invoice_amount_total: float
    transaction_count: int
    reliability_score: float
    risk_classification: str
    recommendation: str
    predicted_delay_probability: Optional[float] = None


class DashboardMetrics(BaseModel):
    total_buyers: int
    average_payment_delay: float
    high_risk_buyers: int
    total_transactions: int = 0
    delay_trend: List[dict]
    risk_distribution: List[dict] = []


class BuyerLookupResponse(BaseModel):
    buyer_name: str
    reliability_score: float
    average_delay: float
    predicted_delay_probability: Optional[float]
    risk_classification: str
    recommendation: str
    late_payment_percentage: Optional[float] = None
    transaction_count: Optional[int] = None
    invoice_amount_total: Optional[float] = None


class TokenResponse(BaseModel):
    access_token: str
    token_type: str


class HealthResponse(BaseModel):
    status: str
    service: str
    database: str


class StatsResponse(BaseModel):
    total_buyers: int
    total_transactions: int
    high_risk_buyers: int
    medium_risk_buyers: int
    low_risk_buyers: int
    average_payment_delay: float
    average_reliability_score: float
    late_payment_rate: float
    receivables_at_risk: float = 0.0


class ModelInfoResponse(BaseModel):
    loaded: bool
    model_type: Optional[str] = None
    accuracy: Optional[float] = None
    accuracy_pct: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    roc_auc: Optional[float] = None
    n_samples: Optional[int] = None
    n_train: Optional[int] = None
    n_test: Optional[int] = None
    features: List[str] = []
    confusion_matrix: Optional[dict] = None
    false_positive_cost_estimate: Optional[float] = None
    false_positive_cost_assumption: Optional[str] = None
    summary: Optional[str] = None


class PredictRequest(BaseModel):
    invoice_amount: float = Field(..., gt=0)
    payment_term_days: int = Field(..., gt=0)
    issue_month: int = Field(..., ge=1, le=12)
    buyer_prior_avg_delay: float = 0.0
    buyer_prior_late_rate: float = 0.0
    buyer_prior_tx_count: int = 0
    buyer_name: Optional[str] = None


class PredictResponse(BaseModel):
    predicted_delay_probability: float
    risk_label: str
    recommendation: str
    buyer_name: Optional[str] = None


class TransactionOut(BaseModel):
    invoice_id: str
    buyer_name: str
    invoice_amount: float
    issue_date: str
    due_date: str
    payment_date: Optional[str]
    payment_delay: Optional[int]


class AgentMessageResponse(BaseModel):
    buyer_name: str
    message: str
    generated_by: str
    risk_classification: Optional[str] = None
    note: Optional[str] = None


class AnalyticsSummary(BaseModel):
    total_buyers: int
    total_transactions: int
    risk_distribution: List[dict]
    top_unreliable_buyers: List[BuyerSummary]
    delay_trend: List[dict]
