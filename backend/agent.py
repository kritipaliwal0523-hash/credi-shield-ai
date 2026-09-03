"""
AI Collections Agent — the "auto-responder" for Track 02.

The brief accepts a detector, a verifier, OR an auto-responder. The rest of
this project is a detector (reliability score + late-payment probability).
This module is the auto-responder half: it takes a buyer's real risk data
(already computed by ml_model.py / analytics.py — nothing here invents
numbers) and asks an LLM to draft a short, risk-appropriate collections /
relationship message a real accounts-receivable team could send.

Design choices, stated plainly:
- Strictly defense-only: this drafts a message for a human to review and
  send. It never sends anything itself, contacts anyone, or takes an
  action on its own.
- If GEMINI_API_KEY isn't set (or the call fails for any reason — no
  network, bad key, rate limit), we fall back to a deterministic
  rule-based template keyed off the same risk classification, so the
  feature still works end-to-end offline and never crashes a live demo.
- The prompt only ever includes numbers already computed elsewhere in the
  app (reliability score, avg delay, late %, predicted probability,
  recommendation) — the model is drafting tone and phrasing, not deciding
  the risk assessment itself.
"""

from __future__ import annotations

import os
from typing import Any, Optional

import requests
from dotenv import load_dotenv

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "").strip()
GEMINI_MODEL = os.getenv("GEMINI_MODEL", "gemini-2.5-flash-lite")
GEMINI_URL = (
    f"https://generativelanguage.googleapis.com/v1beta/models/{GEMINI_MODEL}:generateContent"
)
REQUEST_TIMEOUT_SECONDS = 20


def _build_prompt(
    *,
    buyer_name: str,
    risk_classification: str,
    reliability_score: float,
    average_delay: float,
    late_payment_percentage: float,
    predicted_delay_probability: Optional[float],
    recommendation: str,
    transaction_count: int,
) -> str:
    prob_line = (
        f"Model-predicted probability of late payment on the next invoice: "
        f"{predicted_delay_probability * 100:.1f}%.\n"
        if predicted_delay_probability is not None
        else ""
    )
    return (
        "You are an accounts-receivable assistant at an Indian MSME (small business). "
        "Draft a short, professional message to a business buyer about their payment "
        "reliability. Use the real data below — do not invent numbers. Keep it under "
        "120 words, no markdown, no subject line, sign off as 'Accounts Receivable Team'. "
        "Match tone to risk level: High Risk = firm and direct but polite (ask for a "
        "commitment date or upfront terms); Medium Risk = friendly reminder; "
        "Low Risk = a brief thank-you / good-standing note, not a warning.\n\n"
        f"Buyer: {buyer_name}\n"
        f"Risk classification: {risk_classification}\n"
        f"Reliability score (0-100, higher is better): {reliability_score:.1f}\n"
        f"Average payment delay: {average_delay:.1f} days\n"
        f"Late payment rate: {late_payment_percentage:.1f}% of invoices\n"
        f"{prob_line}"
        f"Number of past transactions on file: {transaction_count}\n"
        f"System recommendation to act on: {recommendation}\n"
    )


def _fallback_message(
    *,
    buyer_name: str,
    risk_classification: str,
    average_delay: float,
    late_payment_percentage: float,
    recommendation: str,
) -> str:
    """Deterministic template used when no API key is configured or the call fails."""
    if risk_classification == "High Risk":
        return (
            f"Dear {buyer_name},\n\n"
            f"Our records show a payment delay pattern on your account — an average of "
            f"{average_delay:.0f} days late, with {late_payment_percentage:.0f}% of invoices "
            f"paid past their due date. To keep our business relationship on track, please "
            f"confirm a firm payment date for any open invoices within 3 business days, or "
            f"let us know if there's a difficulty we should be aware of.\n\n"
            f"Recommended terms going forward: {recommendation}\n\n"
            f"Regards,\nAccounts Receivable Team"
        )
    if risk_classification == "Medium Risk":
        return (
            f"Dear {buyer_name},\n\n"
            f"A friendly reminder — your payment history shows occasional delays "
            f"(average {average_delay:.0f} days). We'd appreciate on-time payment for "
            f"upcoming invoices, and are happy to discuss revised terms if that would help.\n\n"
            f"{recommendation}\n\n"
            f"Regards,\nAccounts Receivable Team"
        )
    return (
        f"Dear {buyer_name},\n\n"
        f"Thank you for being a consistently reliable payer — your account is in good "
        f"standing and no action is needed on our end right now. We look forward to "
        f"continuing to work together.\n\n"
        f"Regards,\nAccounts Receivable Team"
    )


def generate_collection_message(
    *,
    buyer_name: str,
    risk_classification: str,
    reliability_score: float,
    average_delay: float,
    late_payment_percentage: float,
    recommendation: str,
    predicted_delay_probability: Optional[float] = None,
    transaction_count: int = 0,
) -> dict[str, Any]:
    """
    Draft a risk-appropriate message for a buyer.

    Returns a dict with:
      - message: the drafted text
      - generated_by: "gemini" or "fallback_template" (be honest about which ran)
      - risk_classification: echoed back for the UI
    """
    fallback_text = _fallback_message(
        buyer_name=buyer_name,
        risk_classification=risk_classification,
        average_delay=average_delay,
        late_payment_percentage=late_payment_percentage,
        recommendation=recommendation,
    )

    if not GEMINI_API_KEY:
        return {
            "message": fallback_text,
            "generated_by": "fallback_template",
            "risk_classification": risk_classification,
            "note": "GEMINI_API_KEY not set — using rule-based template.",
        }

    prompt = _build_prompt(
        buyer_name=buyer_name,
        risk_classification=risk_classification,
        reliability_score=reliability_score,
        average_delay=average_delay,
        late_payment_percentage=late_payment_percentage,
        predicted_delay_probability=predicted_delay_probability,
        recommendation=recommendation,
        transaction_count=transaction_count,
    )

    try:
        resp = requests.post(
            GEMINI_URL,
            headers={
                "Content-Type": "application/json",
                "x-goog-api-key": GEMINI_API_KEY,
            },
            json={
                "contents": [{"role": "user", "parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.4,
                    "maxOutputTokens": 1024,
                    "thinkingConfig": {"thinkingLevel": "low"},
                },
            },
            timeout=REQUEST_TIMEOUT_SECONDS,
        )
        resp.raise_for_status()
        data = resp.json()
        candidates = data.get("candidates") or []
        parts = candidates[0].get("content", {}).get("parts", []) if candidates else []
        text = "".join(p.get("text", "") for p in parts).strip()
        if not text:
            raise ValueError("Empty response from Gemini")
        return {
            "message": text,
            "generated_by": "gemini",
            "risk_classification": risk_classification,
        }
    except Exception as exc:  # noqa: BLE001 — any failure falls back, demo must not break
        print("GEMINI ERROR:", repr(exc))
        print("GEMINI RESPONSE:", getattr(resp, "text", "NO RESPONSE"))

        return {
            "message": fallback_text,
            "generated_by": "fallback_template",
            "risk_classification": risk_classification,
            "note": f"Gemini call failed ({type(exc).__name__}) — used rule-based template.",
        }