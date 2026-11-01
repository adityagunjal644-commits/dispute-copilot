import json
from paypal_client import list_disputes, get_dispute, add_tracking, get_tracking

dispute = get_dispute(list_disputes()[0]["dispute_id"])
txn_id = dispute["disputed_transactions"][0]["seller_transaction_id"]
print("Transaction:", txn_id)

code, text = add_tracking(txn_id, "BD123456789IN", "BlueDart", "DELIVERED")
print("Upload result:", code)
print(text)

print(json.dumps(get_tracking(txn_id, "BD123456789IN"), indent=2))