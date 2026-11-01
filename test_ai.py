import json
from paypal_client import list_disputes, get_dispute
from evidence import get_evidence
from ai_draft import draft_response

disputes = list_disputes()
dispute = get_dispute(disputes[0]["dispute_id"])

txn_id = dispute["disputed_transactions"][0]["buyer_transaction_id"]
evidence = get_evidence(txn_id)

slim_dispute = {
    "dispute_id": dispute.get("dispute_id"),
    "reason": dispute.get("reason"),
    "status": dispute.get("status"),
    "stage": dispute.get("dispute_life_cycle_stage"),
    "amount": dispute.get("dispute_amount"),
    "created": dispute.get("create_time"),
    "buyer_messages": dispute.get("messages", []),
}

result = draft_response(slim_dispute, evidence)
print(json.dumps(result, indent=2))