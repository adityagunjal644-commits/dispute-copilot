import hmac
import json
import os
from datetime import datetime, timezone

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from paypal_client import list_disputes, get_dispute, send_message, get_transaction
from real_evidence import build_real_evidence
from evidence import get_evidence
from ai_draft import draft_response
from demo_data import DEMO_DISPUTES, DEMO_EVIDENCE

try:
    from paypal_client import get_tracking
except ImportError:
    get_tracking = None

load_dotenv()

app = FastAPI(
    title="AI Dispute Copilot API",
    description="Fetches PayPal disputes, gathers evidence from PayPal and merchant records, asks an AI for a recommendation, stress-tests it with a buyer's-lawyer review, and sends the approved reply back through the PayPal Disputes API. Includes a guardrail-based autopilot and an audit log.",
    version="1.1.0",
)

LOG_FILE = "audit_log.json"
MINUTES_PER_CASE = 25  # assumed manual effort per dispute
APP_PASSCODE = os.getenv("APP_PASSCODE", "")


# ---------- models ----------
class SendBody(BaseModel):
    message: str


class LoginBody(BaseModel):
    passcode: str = ""


class Rules(BaseModel):
    max_amount: float = 100
    min_confidence: float = 0.8
    allowed: list[str] = ["fight", "offer_refund"]
    include_live: bool = False


# ---------- passcode ----------
def passcode_ok(value):
    return hmac.compare_digest((value or "").encode(), APP_PASSCODE.encode())


OPEN_PATHS = ("/api/login", "/api/auth-required")


@app.middleware("http")
async def check_passcode(request: Request, call_next):
    path = request.url.path
    if APP_PASSCODE and path.startswith("/api/") and path not in OPEN_PATHS:
        if not passcode_ok(request.headers.get("x-passcode", "")):
            return JSONResponse({"detail": "Passcode required"}, status_code=401)
    return await call_next(request)


@app.get("/api/auth-required")
def api_auth_required():
    return {"required": bool(APP_PASSCODE)}


@app.post("/api/login")
def api_login(body: LoginBody):
    if APP_PASSCODE and not passcode_ok(body.passcode):
        raise HTTPException(401, "Wrong passcode")
    return {"ok": True}


# ---------- helpers ----------
def is_demo(dispute_id):
    return dispute_id.startswith("DEMO-")


def read_log():
    if not os.path.exists(LOG_FILE):
        return []
    try:
        with open(LOG_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def add_log(entry):
    try:
        log = read_log()
        entry["time"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
        log.append(entry)
        with open(LOG_FILE, "w", encoding="utf-8") as f:
            json.dump(log, f, indent=2)
    except Exception as e:
        print("Could not write audit log:", e)


def to_row(d, source, due=None):
    amt = d.get("dispute_amount", {})
    return {
        "dispute_id": d.get("dispute_id"),
        "reason": d.get("reason"),
        "status": d.get("status"),
        "stage": d.get("dispute_life_cycle_stage"),
        "amount": f"{amt.get('value')} {amt.get('currency_code')}",
        "created": (d.get("create_time") or "")[:10],
        "due": due if due is not None else d.get("seller_response_due_date"),
        "source": source,
    }


def real_rows():
    rows = []
    for d in list_disputes():
        due = d.get("seller_response_due_date")
        if not due:
            try:
                due = get_dispute(d["dispute_id"]).get("seller_response_due_date")
            except (Exception, SystemExit):
                due = None
        rows.append(to_row(d, "PayPal sandbox", due))
    return rows


def analyze_case(dispute_id):
    """Fetch the case, gather evidence, ask the AI. Returns (result, dispute)."""
    if is_demo(dispute_id):
        d = next(x for x in DEMO_DISPUTES if x["dispute_id"] == dispute_id)
        txns = d.get("disputed_transactions") or [{}]
        evidence = DEMO_EVIDENCE.get(txns[0].get("buyer_transaction_id"))
        has_records = evidence is not None
    else:
        d = get_dispute(dispute_id)
        txns = d.get("disputed_transactions") or [{}]
        store = get_evidence(txns[0].get("buyer_transaction_id"))
        real = build_real_evidence(
            d, get_transaction(txns[0].get("seller_transaction_id"))
        )

        track = None
        track_no = (store or {}).get("tracking_number")
        if get_tracking and track_no and txns[0].get("seller_transaction_id"):
            try:
                t = get_tracking(txns[0].get("seller_transaction_id"), track_no)
                track = t if "error" not in t else None
            except (Exception, SystemExit):
                track = None

        evidence = {
            "paypal_data": real,
            "paypal_tracking": track,
            "merchant_records": store,
        }
        has_records = store is not None

    slim = {
        "dispute_id": dispute_id,
        "reason": d.get("reason"),
        "status": d.get("status"),
        "stage": d.get("dispute_life_cycle_stage"),
        "amount": d.get("dispute_amount"),
        "created": d.get("create_time"),
    }
    result = draft_response(slim, evidence)
    result["evidence_found"] = has_records
    return result, d


def log_analysis(dispute_id, result, d):
    st = result.get("stress_test") or {}
    add_log({
        "action": "AI analyzed",
        "dispute_id": dispute_id,
        "strategy": result.get("strategy"),
        "confidence": result.get("confidence"),
        "needs_human_review": result.get("needs_human_review", False),
        "amount": (d.get("dispute_amount") or {}).get("value"),
        "source": "Demo data" if is_demo(dispute_id) else "PayPal sandbox",
        "note": ("Stress test: " + st["severity"] + " risk") if st else "",
    })


def check_guardrails(result, amount, rules):
    reasons = []
    strategy = result.get("strategy")
    conf = float(result.get("confidence") or 0)
    if strategy not in rules.allowed:
        reasons.append(f"strategy '{strategy}' is not allowed")
    if conf < rules.min_confidence:
        reasons.append(
            f"confidence {round(conf * 100)}% is below {round(rules.min_confidence * 100)}%"
        )
    if amount > rules.max_amount:
        reasons.append(f"amount ${amount:g} is above the ${rules.max_amount:g} limit")
    if result.get("needs_human_review"):
        reasons.append("AI asked for human review")
    if not result.get("evidence_found"):
        reasons.append("no merchant records found")
    return reasons


# ---------- routes ----------
@app.get("/api/disputes")
def api_disputes():
    rows = []
    try:
        rows += real_rows()
    except SystemExit as e:
        print("PayPal list failed:", e)
    rows += [to_row(d, "Demo data") for d in DEMO_DISPUTES]
    return rows


@app.post("/api/analyze/{dispute_id}")
def api_analyze(dispute_id: str):
    try:
        result, d = analyze_case(dispute_id)
    except SystemExit as e:
        raise HTTPException(502, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))
    log_analysis(dispute_id, result, d)
    return result


@app.post("/api/autopilot/{dispute_id}")
def api_autopilot(dispute_id: str, rules: Rules):
    try:
        result, d = analyze_case(dispute_id)
    except SystemExit as e:
        raise HTTPException(502, str(e))
    except Exception as e:
        raise HTTPException(500, str(e))

    demo = is_demo(dispute_id)
    source = "Demo data" if demo else "PayPal sandbox"
    amount = float((d.get("dispute_amount") or {}).get("value") or 0)
    log_analysis(dispute_id, result, d)

    reasons = check_guardrails(result, amount, rules)
    if not demo and not rules.include_live:
        reasons.append("live PayPal cases are excluded from autopilot")

    out = {
        "dispute_id": dispute_id,
        "strategy": result.get("strategy"),
        "confidence": result.get("confidence"),
        "amount": amount,
        "reasons": reasons,
    }

    if reasons:
        add_log({
            "action": "Autopilot escalated to human",
            "dispute_id": dispute_id,
            "strategy": result.get("strategy"),
            "confidence": result.get("confidence"),
            "note": "; ".join(reasons)[:120],
            "source": source,
        })
        out["outcome"] = "escalated"
        return out

    if demo:
        add_log({
            "action": "Autopilot approved (demo, not sent)",
            "dispute_id": dispute_id,
            "strategy": result.get("strategy"),
            "confidence": result.get("confidence"),
            "note": result.get("draft_message", "")[:120],
            "source": source,
        })
        out["note"] = "Simulated send (demo data)"
    else:
        try:
            send_message(dispute_id, result["draft_message"])
        except SystemExit as e:
            raise HTTPException(502, str(e))
        add_log({
            "action": "Autopilot approved, sent to PayPal",
            "dispute_id": dispute_id,
            "strategy": result.get("strategy"),
            "confidence": result.get("confidence"),
            "note": result.get("draft_message", "")[:120],
            "source": source,
        })
        out["note"] = "Message sent to PayPal"

    out["outcome"] = "auto"
    return out


@app.post("/api/send/{dispute_id}")
def api_send(dispute_id: str, body: SendBody):
    if is_demo(dispute_id):
        add_log({
            "action": "Human approved (demo, not sent)",
            "dispute_id": dispute_id,
            "note": body.message[:120],
            "source": "Demo data",
        })
        return {"demo": True}
    try:
        reply = send_message(dispute_id, body.message)
    except SystemExit as e:
        raise HTTPException(502, str(e))
    add_log({
        "action": "Human approved, sent to PayPal",
        "dispute_id": dispute_id,
        "note": body.message[:120],
        "source": "PayPal sandbox",
    })
    return reply


@app.get("/api/history")
def api_history():
    return list(reversed(read_log()))[:100]


@app.get("/api/impact")
def api_impact():
    latest = {}
    for e in read_log():
        if e.get("action") == "AI analyzed":
            latest[e["dispute_id"]] = e
    n = len(latest)
    defended = sum(
        float(e.get("amount") or 0) for e in latest.values() if e.get("strategy") == "fight"
    )
    flagged = sum(1 for e in latest.values() if e.get("needs_human_review"))
    return {
        "analyzed": n,
        "minutes_saved": n * MINUTES_PER_CASE,
        "defended_usd": round(defended, 2),
        "human_flagged": flagged,
        "minutes_per_case": MINUTES_PER_CASE,
    }


app.mount("/", StaticFiles(directory="static", html=True), name="static")
