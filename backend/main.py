"""
Buyer Reliability Assessment System — FastAPI entry point.

Interview flow (easy to explain):
1. User logs in -> JWT
2. CSV upload / seed -> analytics + ML train -> SQLite
3. Dashboard / risk table / lookup read from DB
4. /predict uses the saved Logistic Regression model
"""

from __future__ import annotations

from datetime import timedelta
from typing import List

import pandas as pd
from fastapi import Depends, FastAPI, File, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordRequestForm
from sqlalchemy.orm import Session

from . import agent, analytics, ml_model
from .auth import authenticate_user, create_access_token, get_current_user
from .database import Base, engine, get_db
from .ingest import (
    buyer_summaries,
    parse_transactions_csv_bytes,
    replace_all_from_dataframe,
    risk_label_and_recommendation,
    transactions_dataframe,
)
from .models import Buyer, Transaction
from .schemas import (
    AgentMessageResponse,
    AnalyticsSummary,
    BuyerLookupResponse,
    BuyerSummary,
    DashboardMetrics,
    HealthResponse,
    ModelInfoResponse,
    PredictRequest,
    PredictResponse,
    StatsResponse,
    TokenResponse,
    TransactionOut,
)
from .seed import DEFAULT_CSV, clear_and_seed


Base.metadata.create_all(bind=engine)

app = FastAPI(
    title="Buyer Reliability Assessment System",
    description="Analyze MSME buyer payment behaviour with analytics + Logistic Regression.",
    version="1.2.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _to_transaction_out(tx: Transaction, buyer_name: str) -> TransactionOut:
    return TransactionOut(
        invoice_id=tx.invoice_id,
        buyer_name=buyer_name,
        invoice_amount=tx.invoice_amount,
        issue_date=tx.issue_date.isoformat(),
        due_date=tx.due_date.isoformat(),
        payment_date=tx.payment_date.isoformat() if tx.payment_date else None,
        payment_delay=tx.payment_delay,
    )


@app.post("/login", response_model=TokenResponse)
def login(form_data: OAuth2PasswordRequestForm = Depends()) -> TokenResponse:
    user = authenticate_user(form_data.username, form_data.password)
    if not user:
        raise HTTPException(status_code=401, detail="Incorrect email or password")

    token = create_access_token(
        data={"sub": user["email"]},
        expires_delta=timedelta(minutes=60),
    )
    return TokenResponse(access_token=token, token_type="bearer")


@app.get("/health", response_model=HealthResponse)
def health(db: Session = Depends(get_db)) -> HealthResponse:
    try:
        db.query(Buyer).count()
        db_status = "ok"
    except Exception:
        db_status = "error"
    return HealthResponse(
        status="ok" if db_status == "ok" else "degraded",
        service="buyer-reliability-api",
        database=db_status,
    )


@app.post("/upload", response_model=List[BuyerSummary])
async def upload_transactions(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> List[BuyerSummary]:
    contents = await file.read()
    try:
        df = parse_transactions_csv_bytes(contents)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    replace_all_from_dataframe(db, df)
    return buyer_summaries(db)


@app.get("/dashboard", response_model=DashboardMetrics)
def get_dashboard_metrics(
    db: Session = Depends(get_db), _: dict = Depends(get_current_user)
) -> DashboardMetrics:
    summaries = buyer_summaries(db)
    txs = transactions_dataframe(db)
    if not summaries:
        return DashboardMetrics(
            total_buyers=0,
            average_payment_delay=0.0,
            high_risk_buyers=0,
            total_transactions=0,
            delay_trend=[],
            risk_distribution=[],
        )

    per_buyer_df = pd.DataFrame([s.model_dump() for s in summaries])
    metrics = analytics.aggregate_dashboard_metrics(per_buyer_df, txs)
    return DashboardMetrics(
        total_buyers=metrics["total_buyers"],
        average_payment_delay=metrics["average_payment_delay"],
        high_risk_buyers=metrics["high_risk_buyers"],
        total_transactions=int(len(txs)),
        delay_trend=metrics["delay_trend"],
        risk_distribution=analytics.risk_distribution(per_buyer_df),
    )


@app.get("/buyers", response_model=List[BuyerSummary])
def list_buyers(
    db: Session = Depends(get_db), _: dict = Depends(get_current_user)
) -> List[BuyerSummary]:
    return buyer_summaries(db)


@app.get("/buyer/{buyer_name}", response_model=BuyerLookupResponse)
def buyer_lookup(
    buyer_name: str, db: Session = Depends(get_db), _: dict = Depends(get_current_user)
) -> BuyerLookupResponse:
    buyer = db.query(Buyer).filter(Buyer.buyer_name == buyer_name).one_or_none()
    if buyer is None or buyer.reliability_score is None:
        raise HTTPException(status_code=404, detail="Buyer not found")

    score = buyer.reliability_score
    return BuyerLookupResponse(
        buyer_name=buyer.buyer_name,
        reliability_score=score.reliability_score,
        average_delay=score.average_delay,
        predicted_delay_probability=score.predicted_delay_probability,
        risk_classification=score.risk_classification,
        recommendation=score.recommendation or "",
        late_payment_percentage=score.late_payment_percentage,
        transaction_count=len(buyer.transactions),
        invoice_amount_total=sum(t.invoice_amount for t in buyer.transactions),
    )


@app.post("/buyer/{buyer_name}/agent-message", response_model=AgentMessageResponse)
def buyer_agent_message(
    buyer_name: str, db: Session = Depends(get_db), _: dict = Depends(get_current_user)
) -> AgentMessageResponse:
    """
    Auto-responder: draft a risk-appropriate collections / relationship
    message for this buyer, grounded in their real reliability data.
    Uses Gemini if GEMINI_API_KEY is configured, otherwise a rule-based
    fallback template — either way this never invents a risk assessment,
    it only phrases the one already computed by the model.
    """
    buyer = db.query(Buyer).filter(Buyer.buyer_name == buyer_name).one_or_none()
    if buyer is None or buyer.reliability_score is None:
        raise HTTPException(status_code=404, detail="Buyer not found")

    score = buyer.reliability_score
    result = agent.generate_collection_message(
        buyer_name=buyer.buyer_name,
        risk_classification=score.risk_classification,
        reliability_score=score.reliability_score,
        average_delay=score.average_delay,
        late_payment_percentage=score.late_payment_percentage,
        recommendation=score.recommendation or "",
        predicted_delay_probability=score.predicted_delay_probability,
        transaction_count=len(buyer.transactions),
    )
    return AgentMessageResponse(buyer_name=buyer.buyer_name, **result)


@app.get("/buyer/{buyer_name}/history", response_model=List[TransactionOut])
def buyer_history(
    buyer_name: str, db: Session = Depends(get_db), _: dict = Depends(get_current_user)
) -> List[TransactionOut]:
    buyer = db.query(Buyer).filter(Buyer.buyer_name == buyer_name).one_or_none()
    if buyer is None:
        raise HTTPException(status_code=404, detail="Buyer not found")

    ordered = sorted(buyer.transactions, key=lambda t: t.issue_date, reverse=True)
    return [_to_transaction_out(tx, buyer.buyer_name) for tx in ordered]


@app.get("/transactions", response_model=List[TransactionOut])
def list_transactions(
    limit: int = Query(100, ge=1, le=1000),
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> List[TransactionOut]:
    rows = (
        db.query(Transaction, Buyer.buyer_name)
        .join(Buyer, Transaction.buyer_id == Buyer.id)
        .order_by(Transaction.issue_date.desc())
        .limit(limit)
        .all()
    )
    return [_to_transaction_out(tx, buyer_name) for tx, buyer_name in rows]


@app.get("/stats", response_model=StatsResponse)
def portfolio_stats(
    db: Session = Depends(get_db), _: dict = Depends(get_current_user)
) -> StatsResponse:
    summaries = buyer_summaries(db)
    txs = transactions_dataframe(db)
    if not summaries:
        return StatsResponse(
            total_buyers=0,
            total_transactions=0,
            high_risk_buyers=0,
            medium_risk_buyers=0,
            low_risk_buyers=0,
            average_payment_delay=0.0,
            average_reliability_score=0.0,
            late_payment_rate=0.0,
            receivables_at_risk=0.0,
        )

    high = sum(1 for s in summaries if s.risk_classification == "High Risk")
    medium = sum(1 for s in summaries if s.risk_classification == "Medium Risk")
    low = sum(1 for s in summaries if s.risk_classification == "Low Risk")

    late_rate = 0.0
    if not txs.empty:
        due = pd.to_datetime(txs["due_date"])
        paid = pd.to_datetime(txs["payment_date"])
        late_rate = float(((paid - due).dt.days > 0).mean() * 100.0)

    # Revenue-recovery framing: total invoice value sitting with buyers the
    # AI Collections Agent has flagged High Risk — the "money at risk" this
    # project can act on today.
    receivables_at_risk = sum(
        s.invoice_amount_total for s in summaries if s.risk_classification == "High Risk"
    )

    return StatsResponse(
        total_buyers=len(summaries),
        total_transactions=int(len(txs)),
        high_risk_buyers=high,
        medium_risk_buyers=medium,
        low_risk_buyers=low,
        average_payment_delay=sum(s.average_delay for s in summaries) / len(summaries),
        average_reliability_score=sum(s.reliability_score for s in summaries) / len(summaries),
        late_payment_rate=late_rate,
        receivables_at_risk=receivables_at_risk,
    )


@app.get("/analytics/summary", response_model=AnalyticsSummary)
def analytics_summary(
    db: Session = Depends(get_db), _: dict = Depends(get_current_user)
) -> AnalyticsSummary:
    summaries = buyer_summaries(db)
    txs = transactions_dataframe(db)
    per_buyer_df = (
        pd.DataFrame([s.model_dump() for s in summaries]) if summaries else pd.DataFrame()
    )
    top = sorted(summaries, key=lambda s: s.reliability_score)[:5]
    return AnalyticsSummary(
        total_buyers=len(summaries),
        total_transactions=int(len(txs)),
        risk_distribution=analytics.risk_distribution(per_buyer_df)
        if not per_buyer_df.empty
        else [],
        top_unreliable_buyers=top,
        delay_trend=analytics.build_delay_trend(txs),
    )


@app.get("/model/info", response_model=ModelInfoResponse)
def model_info(_: dict = Depends(get_current_user)) -> ModelInfoResponse:
    model = ml_model.load_model()
    if model is None:
        return ModelInfoResponse(loaded=False, summary="No model trained yet. Upload data first.")

    m = model.metrics
    accuracy_pct = m.get("accuracy_pct")
    precision = m.get("precision")
    recall = m.get("recall")
    fp_cost = m.get("false_positive_cost_estimate")
    summary = (
        f"Logistic Regression trained on late-payment prediction. "
        f"Holdout accuracy: {accuracy_pct}%, precision: {precision}, recall: {recall}."
        + (f" Estimated false-positive cost: ₹{fp_cost}." if fp_cost is not None else "")
        if accuracy_pct is not None
        else "Logistic Regression model loaded."
    )
    return ModelInfoResponse(
        loaded=True,
        model_type=m.get("model_type", "LogisticRegression"),
        accuracy=m.get("accuracy"),
        accuracy_pct=accuracy_pct,
        precision=precision,
        recall=recall,
        roc_auc=m.get("roc_auc"),
        n_samples=m.get("n_samples"),
        n_train=m.get("n_train"),
        n_test=m.get("n_test"),
        features=m.get("features", ml_model.FEATURE_COLUMNS),
        confusion_matrix=m.get("confusion_matrix"),
        false_positive_cost_estimate=fp_cost,
        false_positive_cost_assumption=m.get("false_positive_cost_assumption"),
        summary=summary,
    )


@app.post("/predict", response_model=PredictResponse)
def predict_risk(
    payload: PredictRequest,
    db: Session = Depends(get_db),
    _: dict = Depends(get_current_user),
) -> PredictResponse:
    model = ml_model.load_model()
    if model is None:
        txs = transactions_dataframe(db)
        if txs.empty:
            raise HTTPException(
                status_code=400, detail="No trained model. Upload transaction data first."
            )
        model = ml_model.train_delay_model(txs)
        if model is None:
            raise HTTPException(status_code=400, detail="Unable to train prediction model.")

    prior_avg = payload.buyer_prior_avg_delay
    prior_late = payload.buyer_prior_late_rate
    prior_count = payload.buyer_prior_tx_count
    prior_avg_amount = None
    late_streak = 0
    buyer_name = payload.buyer_name

    if buyer_name:
        buyer = db.query(Buyer).filter(Buyer.buyer_name == buyer_name).one_or_none()
        if buyer and buyer.reliability_score is not None:
            prior_avg = buyer.reliability_score.average_delay
            prior_late = buyer.reliability_score.late_payment_percentage
            prior_count = len(buyer.transactions)
            if buyer.transactions:
                prior_avg_amount = sum(t.invoice_amount for t in buyer.transactions) / len(
                    buyer.transactions
                )
                ordered = sorted(
                    [t for t in buyer.transactions if t.payment_date and t.due_date],
                    key=lambda t: t.issue_date,
                )
                for tx in reversed(ordered):
                    if (tx.payment_date - tx.due_date).days > 0:
                        late_streak += 1
                    else:
                        break

    proba = ml_model.predict_single(
        model,
        invoice_amount=payload.invoice_amount,
        payment_term_days=payload.payment_term_days,
        issue_month=payload.issue_month,
        buyer_prior_avg_delay=prior_avg,
        buyer_prior_late_rate=prior_late,
        buyer_prior_tx_count=prior_count,
        buyer_prior_avg_amount=prior_avg_amount,
        buyer_late_streak=late_streak,
    )
    label, recommendation = risk_label_and_recommendation(
    proba,
    average_delay=prior_avg,
    late_payment_percentage=prior_late,)
    return PredictResponse(
        predicted_delay_probability=proba,
        risk_label=label,
        recommendation=recommendation,
        buyer_name=buyer_name,
    )


@app.post("/admin/seed")
def seed_database(
    db: Session = Depends(get_db), _: dict = Depends(get_current_user)
) -> dict:
    if not DEFAULT_CSV.exists():
        raise HTTPException(status_code=404, detail="Sample dataset not found.")
    result = clear_and_seed(db, DEFAULT_CSV)
    return {"status": "seeded", **result}
