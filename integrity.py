"""Evidence integrity checks: find contradictions across the sources we hold.

All detection is plain code, so every finding is real.
Nothing here asks the AI to invent a contradiction.
"""
from datetime import datetime

WEAK_WORDS = (
    "neighbour", "neighbor", "unreadable", "illegible", "guard",
    "no signature", "unsigned", "left with", "left at",
)
STRONG_WORDS = ("otp", "gps", "photo")
PENALTY = {"high": 0.15, "medium": 0.05}
MAX_PENALTY = 0.25


def _date(value):
    try:
        return datetime.strptime(str(value)[:10], "%Y-%m-%d").date()
    except (ValueError, TypeError):
        return None


def _num(value):
    if isinstance(value, dict):
        value = value.get("value")
    try:
        return abs(float(str(value).replace(",", "")))
    except (ValueError, TypeError):
        return None


def _finding(title, severity, detail, sources, check):
    return {
        "title": title,
        "severity": severity,
        "detail": detail,
        "sources": sources,
        "check": check,
    }


def _summary(findings, sources):
    findings = sorted(findings, key=lambda f: 0 if f["severity"] == "high" else 1)
    high = sum(1 for f in findings if f["severity"] == "high")
    medium = sum(1 for f in findings if f["severity"] == "medium")
    penalty = min(MAX_PENALTY, high * PENALTY["high"] + medium * PENALTY["medium"])

    if high:
        first = next(f for f in findings if f["severity"] == "high")
        action = "Do not submit evidence yet. " + first["check"] + " before responding."
    elif medium:
        action = ("Review these points before sending. If they cannot be resolved, "
                  "a refund offer is safer than a fight.")
    elif len(sources) >= 2:
        action = "No contradictions found across the sources compared."
    else:
        action = "Too little data to compare."

    return {
        "count": len(findings),
        "high": high,
        "medium": medium,
        "findings": findings,
        "sources": sources,
        "recommended_action": action,
        "penalty": round(penalty, 2),
    }


def check_integrity(dispute, evidence):
    dispute = dispute or {}
    if not isinstance(evidence, dict) or not evidence:
        return _summary([], [])

    # Live cases nest their sources; demo cases are one flat record.
    if "merchant_records" in evidence:
        records = evidence.get("merchant_records")
    else:
        records = evidence
    records = records if isinstance(records, dict) else {}

    paypal = evidence.get("paypal_data")
    paypal = paypal if isinstance(paypal, dict) else {}
    tracker = evidence.get("paypal_tracking")
    tracker = tracker if isinstance(tracker, dict) else None
    courier = records.get("courier_tracking")
    courier = courier if isinstance(courier, dict) else None
    ext = tracker or courier
    ext_name = "PayPal tracking" if tracker else "Courier tracking"
    txn = paypal.get("paypal_transaction")
    txn = txn if isinstance(txn, dict) else {}

    sources = []
    if records:
        sources.append("Merchant records")
    if ext:
        sources.append(ext_name)
    if txn:
        sources.append("PayPal transaction")
    # if records.get("customer_messages") or paypal.get("buyer_complaint_messages"):
    #     sources.append("Buyer messages")
    if dispute.get("create_time"):
        sources.append("Dispute timeline")

    ordered = _date(records.get("ordered_on"))
    shipped = _date(records.get("shipped_on"))
    delivered = _date(records.get("delivered_on"))
    created = _date(dispute.get("create_time"))
    status = str(records.get("tracking_status") or "").upper()

    out = []

    if ordered and shipped and shipped < ordered:
        out.append(_finding(
            "Shipped before it was ordered", "high",
            f"Merchant records show shipping on {shipped} but the order on {ordered}.",
            ["Merchant records"], "Verify the order and shipping dates in your order system"))

    if shipped and delivered and delivered < shipped:
        out.append(_finding(
            "Delivered before it shipped", "high",
            f"Merchant records show delivery on {delivered} but shipping on {shipped}.",
            ["Merchant records"], "Verify the shipping and delivery dates with the courier"))

    if courier and delivered:
        c_date = _date(courier.get("delivered_on"))
        if c_date and c_date != delivered:
            gap = abs((c_date - delivered).days)
            out.append(_finding(
                "Delivery date mismatch", "high" if gap >= 3 else "medium",
                f"Merchant records say delivered {delivered}, courier tracking says "
                f"{c_date} ({gap} day{'s' if gap != 1 else ''} apart).",
                ["Merchant records", "Courier tracking"],
                "Verify the courier's official delivery scan date and time"))

    if ext:
        e_status = str(ext.get("status") or "").upper()
        if status and e_status and e_status != status:
            out.append(_finding(
                "Tracking status mismatch", "high",
                f"Merchant records say {status}, {ext_name} says {e_status}.",
                ["Merchant records", ext_name],
                "Verify the current tracking status with the courier"))
        r_no, e_no = records.get("tracking_number"), ext.get("tracking_number")
        if r_no and e_no and str(r_no).strip() != str(e_no).strip():
            out.append(_finding(
                "Tracking number mismatch", "high",
                f"Merchant records list {r_no}, {ext_name} lists {e_no}.",
                ["Merchant records", ext_name],
                "Verify which tracking number belongs to this order"))

    proof = str(records.get("delivery_proof") or "").strip()
    if status == "DELIVERED" and not proof:
        out.append(_finding(
            "No proof of delivery", "medium",
            "The order is marked delivered but no delivery proof is on file.",
            ["Merchant records"], "Ask the courier for a signed or OTP/GPS-verified delivery record"))
    elif proof:
        low = proof.lower()
        if any(w in low for w in WEAK_WORDS) and not any(s in low for s in STRONG_WORDS):
            out.append(_finding(
                "Weak delivery confirmation", "medium",
                f"Delivery proof is weak: \"{proof}\".",
                ["Merchant records"],
                "Ask the courier for a signed or OTP/GPS-verified delivery record"))

    if created and delivered and created < delivered:
        out.append(_finding(
            "Dispute opened before delivery", "medium",
            f"The buyer opened the dispute on {created}, before the recorded delivery date {delivered}.",
            ["Dispute timeline", "Merchant records"],
            "Check whether the parcel really arrived after the buyer complained"))

    m_amt = _num(records.get("amount_usd"))
    p_amt = _num(txn.get("amount"))
    if m_amt is not None and p_amt is not None and abs(m_amt - p_amt) > 0.01:
        out.append(_finding(
            "Payment amount mismatch", "high",
            f"Merchant records show ${m_amt:.2f} but the PayPal transaction shows ${p_amt:.2f}.",
            ["Merchant records", "PayPal transaction"],
            "Verify the order total against the PayPal payment"))

    return _summary(out, sources)