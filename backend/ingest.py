"""Shared data loading helpers.

Upload and seed both call the same pipeline so analytics + ML stay consistent.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pandas as pd
from sqlalchemy.orm import Session

from . import analytics, ml_model
from .models import Buyer, ReliabilityScore, Transaction
from .schemas import BuyerSummary


REQUIRED_CSV_COLUMNS = [
    "invoice_id",
    "buyer_name",
    "invoice_amount",
    "issue_date",
    "due_date",
    "payment_date",
]


def parse_transactions_csv_bytes(file_bytes: bytes) -> pd.DataFrame:
    df = pd.read_csv(pd.io.common.BytesIO(file_bytes))
    return _normalize_transaction_df(df)


def parse_transactions_csv_path(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    return _normalize_transaction_df(df)


def _normalize_transaction_df(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in REQUIRED_CSV_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns: {', '.join(missing)}")

    out = df.copy()
    for col in ["issue_date", "due_date", "payment_date"]:
        out[col] = pd.to_datetime(out[col], errors="coerce")
    return out


def transactions_dataframe(db: Session) -> pd.DataFrame:
    """Load all stored transactions into a pandas DataFrame."""
    rows = (
        db.query(Transaction, Buyer.buyer_name)
        .join(Buyer, Transaction.buyer_id == Buyer.id)
        .all()
    )
    if not rows:
        return pd.DataFrame(columns=REQUIRED_CSV_COLUMNS)

    return pd.DataFrame(
        [
            {
                "invoice_id": tx.invoice_id,
                "buyer_name": buyer_name,
                "invoice_amount": tx.invoice_amount,
                "issue_date": tx.issue_date,
                "due_date": tx.due_date,
                "payment_date": tx.payment_date,
            }
            for tx, buyer_name in rows
        ]
    )


def buyer_summaries(db: Session) -> list[BuyerSummary]:
    scores = db.query(ReliabilityScore).all()
    return [
        BuyerSummary(
            buyer_name=s.buyer.buyer_name,
            average_delay=s.average_delay,
            late_payment_percentage=s.late_payment_percentage,
            invoice_amount_total=sum(t.invoice_amount for t in s.buyer.transactions),
            transaction_count=len(s.buyer.transactions),
            reliability_score=s.reliability_score,
            risk_classification=s.risk_classification,
            recommendation=s.recommendation or "",
            predicted_delay_probability=s.predicted_delay_probability,
        )
        for s in scores
    ]


def replace_all_from_dataframe(db: Session, df: pd.DataFrame) -> dict:
    """
    Clear existing data, recompute analytics, retrain ML, and save everything.

    Returns a small summary useful for seed scripts and API responses.
    """
    per_buyer = analytics.compute_payment_delay_metrics(df)
    model = ml_model.train_delay_model(df)
    buyer_probs = (
        ml_model.predict_buyer_delay_probabilities(model, df) if model is not None else {}
    )

    db.query(ReliabilityScore).delete()
    db.query(Transaction).delete()
    db.query(Buyer).delete()
    db.flush()

    buyers_by_name: dict[str, Buyer] = {}
    for _, row in per_buyer.iterrows():
        buyer = Buyer(buyer_name=row["buyer_name"])
        db.add(buyer)
        db.flush()
        buyers_by_name[row["buyer_name"]] = buyer

        predicted = buyer_probs.get(row["buyer_name"])
        db.add(
            ReliabilityScore(
                buyer_id=buyer.id,
                average_delay=float(row["average_delay"]),
                late_payment_percentage=float(row["late_payment_percentage"]),
                reliability_score=float(row["reliability_score"]),
                predicted_delay_probability=float(predicted) if predicted is not None else None,
                risk_classification=row["risk_classification"],
                recommendation=row["recommendation"],
                updated_at=datetime.utcnow().date(),
            )
        )

    for _, row in df.iterrows():
        buyer = buyers_by_name[row["buyer_name"]]
        db.add(
            Transaction(
                invoice_id=row["invoice_id"],
                buyer_id=buyer.id,
                invoice_amount=float(row["invoice_amount"]),
                issue_date=row["issue_date"].date(),
                due_date=row["due_date"].date(),
                payment_date=row["payment_date"].date()
                if pd.notnull(row["payment_date"])
                else None,
            )
        )

    db.commit()

    metrics = model.metrics if model is not None else {}
    return {
        "buyers": len(buyers_by_name),
        "transactions": int(len(df)),
        "model_accuracy_pct": metrics.get("accuracy_pct"),
    }


def risk_label_and_recommendation(
    probability: float,
    average_delay: float = 0.0,
    late_payment_percentage: float = 0.0,
) -> tuple[str, str]:
    """Map prediction + buyer history to a buyer-specific risk recommendation."""

    if probability >= 0.66:
        label = "High Risk"
    elif probability >= 0.4:
        label = "Medium Risk"
    else:
        label = "Low Risk"

    avg_delay = float(average_delay)
    late_rate = float(late_payment_percentage)

    if avg_delay <= -1 and late_rate <= 10:
        recommendation = (
            "Maintain standard payment terms. Buyer consistently pays early "
            "or on time; consider maintaining their existing credit limit."
        )
    elif avg_delay <= 1 and late_rate <= 20:
        recommendation = (
            "Maintain standard terms with automated reminders before the due date. "
            "Monitor occasional late payments rather than tightening terms."
        )
    elif avg_delay <= 5 and late_rate <= 35:
        recommendation = (
            "Use shorter payment terms for larger invoices and send proactive "
            "payment reminders. Review the buyer's trend before increasing credit."
        )
    elif avg_delay > 5 or late_rate > 35:
        recommendation = (
            "Tighten credit exposure: consider partial upfront payment, shorter "
            "terms, and a credit-limit review for larger invoices."
        )
    elif label == "High Risk":
        recommendation = "Require stronger payment protection and review credit exposure."
    elif label == "Medium Risk":
        recommendation = "Use shorter terms and monitor payment behaviour closely."
    else:
        recommendation = "Maintain standard payment terms and monitor payment behaviour."

    return label, recommendation

