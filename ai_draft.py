import json
import os

from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()

client = genai.Client(
    api_key=os.getenv("GEMINI_API_KEY"),
    http_options=types.HttpOptions(timeout=30000),
)

# The first model is tried first. If it fails, the next one is used.
MODELS = [
    "gemini-3.5-flash-lite",
    "gemini-flash-lite-latest",
    "gemini-flash-latest",
]

PROMPT = """You are a dispute assistant for a small online merchant.
A customer opened a PayPal dispute. Decide how the merchant should respond,
using ONLY the facts provided. Do not invent facts.

DISPUTE:
{dispute}

MERCHANT RECORDS (order, shipping, messages):
{evidence}

Rules for the decision:
- "fight": only when the records clearly disprove the buyer's claim.
- "offer_refund": when the records are weak, the buyer's claim is plausible, or the amount is small.
- "accept": when the records support the buyer's claim.
- If there are no records, confidence must be below 0.4, win_probability below 0.3, and needs_human_review must be true.
- Never give confidence or win_probability above 0.9. Delivery proof can be wrong, so keep some doubt.
- Set needs_human_review to true whenever confidence is below 0.7.
- The draft_message must match the strategy. For "offer_refund", it must clearly offer a full refund of the dispute amount. For "fight", it must present the evidence. For "accept", it must agree to refund. Never promise a future update instead of taking the chosen action.
- For "offer_refund" and "accept", the draft_message must be short, friendly and neutral. It must not describe weaknesses in the merchant's own records (such as unreadable signatures, delivery to a neighbour, missing proof or delays). Just apologise briefly, offer the refund, and thank the buyer. For "fight", present only the strongest evidence.

Reply with JSON only, using exactly these keys:
- "strategy": one of "fight", "offer_refund", "accept"
- "confidence": number from 0 to 1 (how sure you are that this strategy is the right call)
- "win_probability": number from 0 to 1 (your honest estimate of the chance the merchant WINS if they contest this dispute, whatever strategy you recommend)
- "needs_human_review": true or false
- "evidence_used": list of short strings, each naming a fact you relied on
- "reasoning": 2-3 sentences explaining the decision
- "draft_message": a polite, professional message to send to PayPal/the buyer
- "evidence_plan": an object with three keys. "items": a list of up to 4 short strings naming extra evidence the merchant could realistically collect that is NOT already in the records (for example buyer chat history, photos, courier call logs). If the records already hold strong proof, return an empty list. "days_needed": a whole number, the days needed to collect it. "win_boost": a number from 0 to 0.25, how much that evidence would raise win_probability. If "items" is empty, days_needed and win_boost must be 0.
- "scenario_notes": an object with four keys: "fight", "partial_refund", "accept", "wait". Each value is an object with two short sentences: "risk" (the main risk of that option for this case) and "next_step" (the single next action).
"""

STRESS_PROMPT = """You are a sharp lawyer representing the BUYER in a PayPal dispute.
Your job is to attack the merchant's position, using ONLY the facts provided.
Do not invent facts.

DISPUTE:
{dispute}

MERCHANT RECORDS:
{evidence}

MERCHANT'S RECOMMENDED STRATEGY: {strategy}

MERCHANT'S DRAFT MESSAGE:
{draft}

Find the strongest honest weaknesses in the merchant's case or message: missing
proof, unclear signatures, timing gaps, claims in the draft that the records do
not support, tone problems.

Reply with JSON only, using exactly these keys:
- "buyer_counterargument": the buyer's strongest argument, in 1-2 sentences
- "weak_points": list of up to 3 short strings
- "severity": one of "low", "medium", "high" (how much damage these weak points do to the merchant's position)
- "revised_draft_message": the merchant's draft rewritten to address the weak points. Keep the same strategy (for "offer_refund" it must still clearly offer a full refund of the dispute amount) and use only the provided facts. Do not volunteer weaknesses or admissions against the merchant in the revised message. Address concerns neutrally and stay polite. If the draft is already solid, return it unchanged.
"""

SEVERITY_PENALTY = {"low": 0.0, "medium": 0.10, "high": 0.20}


def _generate_json(prompt):
    last_error = None
    for model in MODELS:
        try:
            response = client.models.generate_content(
                model=model,
                contents=prompt,
                config={"response_mime_type": "application/json"},
            )
            data = json.loads(response.text)
            if isinstance(data, list) and data:
                data = data[0]
            if not isinstance(data, dict):
                raise ValueError("AI did not return a JSON object")
            return data
        except Exception as e:
            last_error = e
            print(f"Model {model} failed: {e}")
    raise RuntimeError(f"All AI models failed. Last error: {last_error}")


def _num(value, default, lo=0.0, hi=1.0):
    try:
        v = float(value)
    except (TypeError, ValueError):
        v = default
    return max(lo, min(v, hi))


def _clean_plan(result):
    plan = result.get("evidence_plan")
    plan = plan if isinstance(plan, dict) else {}

    items = plan.get("items")
    items = [str(i) for i in items][:4] if isinstance(items, list) else []

    try:
        days = int(plan.get("days_needed", 3))
    except (TypeError, ValueError):
        days = 3
    days = max(0, min(days, 30))

    result["evidence_plan"] = {
        "items": items,
        "days_needed": days,
        "win_boost": _num(plan.get("win_boost"), 0.1, 0.0, 0.25),
    }

    notes = result.get("scenario_notes")
    notes = notes if isinstance(notes, dict) else {}
    clean = {}
    for key in ("fight", "partial_refund", "accept", "wait"):
        n = notes.get(key)
        n = n if isinstance(n, dict) else {}
        clean[key] = {
            "risk": str(n.get("risk") or ""),
            "next_step": str(n.get("next_step") or ""),
        }
    result["scenario_notes"] = clean


def _normalize(result):
    flag = bool(result.get("needs_human_review"))
    if result.get("strategy") not in ("fight", "offer_refund", "accept"):
        result["strategy"] = "offer_refund"
        flag = True
    result["confidence"] = _num(result.get("confidence"), 0.5, 0.0, 0.9)
    result["win_probability"] = _num(result.get("win_probability"), 0.5, 0.0, 0.9)
    if result["confidence"] < 0.7:
        flag = True
    result["needs_human_review"] = flag
    if not isinstance(result.get("evidence_used"), list):
        result["evidence_used"] = []
    result["reasoning"] = str(result.get("reasoning") or "")
    result["draft_message"] = str(result.get("draft_message") or "")
    _clean_plan(result)
    return result


def _stress_test(dispute, evidence, result):
    prompt = STRESS_PROMPT.format(
        dispute=json.dumps(dispute, indent=2, default=str),
        evidence=json.dumps(evidence, indent=2, default=str),
        strategy=result["strategy"],
        draft=result["draft_message"],
    )
    data = _generate_json(prompt)

    severity = data.get("severity")
    if severity not in SEVERITY_PENALTY:
        severity = "medium"
    penalty = SEVERITY_PENALTY[severity]

    weak = data.get("weak_points")
    weak = [str(w) for w in weak][:3] if isinstance(weak, list) else []

    original = result["draft_message"]
    revised = str(data.get("revised_draft_message") or "").strip() or original

    before = result["confidence"]
    after = round(max(0.05, before - penalty), 2)

    result["confidence"] = after
    result["win_probability"] = round(max(0.0, result["win_probability"] - penalty), 2)
    result["draft_message"] = revised
    if severity == "high" or after < 0.7:
        result["needs_human_review"] = True

    result["stress_test"] = {
        "buyer_counterargument": str(data.get("buyer_counterargument") or ""),
        "weak_points": weak,
        "severity": severity,
        "confidence_before": before,
        "confidence_after": after,
        "draft_changed": revised != original.strip(),
        "original_draft_message": original,
    }


def draft_response(dispute, evidence, stress=True):
    prompt = PROMPT.format(
        dispute=json.dumps(dispute, indent=2, default=str),
        evidence=json.dumps(evidence, indent=2, default=str) if evidence else "No records found.",
    )
    result = _normalize(_generate_json(prompt))
    result["stress_test"] = None

    if stress and evidence:
        try:
            _stress_test(dispute, evidence, result)
        except Exception as e:
            print("Stress test failed:", e)
    return result