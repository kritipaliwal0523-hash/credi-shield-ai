"""Rule-based buyer payment analytics.

Interview explanation:
- payment_delay = payment_date - due_date
- reliability_score starts at 100 and penalizes delay + late %
- risk bands: Low (>=80), Medium (>=60), High (<60)
"""

from __future__ import annotations

import pandas as pd


def compute_payment_delay_metrics(df: pd.DataFrame) -> pd.DataFrame:
    """
    Expects columns: buyer_name, invoice_id, invoice_amount, due_date, payment_date.
    due_date/payment_date should be datetime-like.
    """
    df = df.copy()
    df["payment_delay"] = (df["payment_date"] - df["due_date"]).dt.days
    df["is_late"] = df["payment_delay"] > 0

    grouped = df.groupby("buyer_name").agg(
        average_delay=("payment_delay", "mean"),
        late_payment_percentage=("is_late", "mean"),
        invoice_amount_total=("invoice_amount", "sum"),
        transaction_count=("invoice_id", "count"),
    )

    grouped["late_payment_percentage"] = grouped["late_payment_percentage"] * 100.0

    grouped["reliability_score"] = (
        100
        - grouped["average_delay"].clip(lower=0) * 1.5
        - grouped["late_payment_percentage"] * 0.5
    ).clip(lower=0, upper=100)

    def classify(r: pd.Series) -> str:
        if r["reliability_score"] >= 80:
            return "Low Risk"
        if r["reliability_score"] >= 60:
            return "Medium Risk"
        return "High Risk"

    grouped["risk_classification"] = grouped.apply(classify, axis=1)

    def recommend(r: pd.Series) -> str:
        avg_delay = float(r["average_delay"])
        late_rate = float(r["late_payment_percentage"])
        risk = r["risk_classification"]

        # Strong track record: usually early/on-time with very few late invoices.
        if avg_delay <= -1 and late_rate <= 10:
            return (
                "Maintain standard payment terms. Buyer consistently pays early "
                "or on time; consider maintaining their existing credit limit."
            )

        # Generally reliable, but occasional late payments.
        if avg_delay <= 1 and late_rate <= 20:
            return (
                "Maintain standard terms with automated reminders before the due date. "
                "Monitor occasional late payments rather than tightening terms."
            )

        # Moderate payment friction.
        if avg_delay <= 5 and late_rate <= 35:
            return (
                "Use shorter payment terms for larger invoices and send proactive "
                "payment reminders. Review the buyer's trend before increasing credit."
            )

        # Persistent late-payment behaviour.
        if avg_delay > 5 or late_rate > 35:
            return (
                "Tighten credit exposure: consider partial upfront payment, shorter "
                "terms, and a credit-limit review for larger invoices."
            )

        # Safety fallback based on overall risk.
        if risk == "High Risk":
            return "Require stronger payment protection and review credit exposure."
        if risk == "Medium Risk":
            return "Use shorter terms and monitor payment behaviour closely."
        return "Maintain standard payment terms and monitor payment behaviour."
    
    grouped["recommendation"] = grouped.apply(recommend, axis=1)
    return grouped



def build_delay_trend(transactions_df: pd.DataFrame) -> list[dict]:
    """Monthly average payment delay from transaction-level data."""
    if transactions_df is None or transactions_df.empty:
        return []

    df = transactions_df.copy()
    df["due_date"] = pd.to_datetime(df["due_date"])
    df["payment_date"] = pd.to_datetime(df["payment_date"])
    df["payment_delay"] = (df["payment_date"] - df["due_date"]).dt.days
    df["month"] = df["due_date"].dt.to_period("M").astype(str)

    trend = (
        df.groupby("month", as_index=False)["payment_delay"]
        .mean()
        .rename(columns={"month": "label", "payment_delay": "value"})
        .sort_values("label")
    )
    return [
        {"label": row["label"], "value": float(row["value"])}
        for _, row in trend.iterrows()
    ]


def aggregate_dashboard_metrics(
    per_buyer: pd.DataFrame, transactions_df: pd.DataFrame | None = None
) -> dict:
    total_buyers = int(per_buyer["buyer_name"].nunique()) if not per_buyer.empty else 0
    avg_delay = float(per_buyer["average_delay"].mean()) if total_buyers else 0.0
    high_risk = (
        int(
            per_buyer[per_buyer["risk_classification"] == "High Risk"][
                "buyer_name"
            ].nunique()
        )
        if total_buyers
        else 0
    )

    delay_trend = build_delay_trend(transactions_df) if transactions_df is not None else []

    return {
        "total_buyers": total_buyers,
        "average_payment_delay": avg_delay,
        "high_risk_buyers": high_risk,
        "delay_trend": delay_trend,
    }


def risk_distribution(per_buyer: pd.DataFrame) -> list[dict]:
    if per_buyer is None or per_buyer.empty:
        return []
    counts = per_buyer["risk_classification"].value_counts().to_dict()
    order = ["Low Risk", "Medium Risk", "High Risk"]
    return [{"name": name, "value": int(counts.get(name, 0))} for name in order]
