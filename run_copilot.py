import json
from paypal_client import list_disputes, get_dispute, send_message
from evidence import get_evidence
from ai_draft import draft_response

disputes = list_disputes()
dispute = get_dispute(disputes[0]["dispute_id"])
dispute_id = dispute["dispute_id"]

txn_id = dispute["disputed_transactions"][0]["buyer_transaction_id"]
evidence = get_evidence(txn_id)

slim = {
    "dispute_id": dispute_id,
    "reason": dispute.get("reason"),
    "status": dispute.get("status"),
    "stage": dispute.get("dispute_life_cycle_stage"),
    "amount": dispute.get("dispute_amount"),
    "created": dispute.get("create_time"),
}

result = draft_response(slim, evidence)

print("\n=== AI RECOMMENDATION ===")
print("Strategy:   ", result["strategy"])
print("Confidence: ", result["confidence"])
print("Reasoning:  ", result["reasoning"])
print("\nDraft message:\n", result["draft_message"])

answer = input("\nApprove and send to PayPal? (yes/no): ").strip().lower()
if answer == "yes":
    reply = send_message(dispute_id, result["draft_message"])
    print("\nSent. PayPal replied:")
    print(json.dumps(reply, indent=2))
else:
    print("Not sent. Nothing changed.")