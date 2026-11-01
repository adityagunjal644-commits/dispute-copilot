import json
from paypal_client import list_disputes, get_dispute, get_transaction

dispute = get_dispute(list_disputes()[0]["dispute_id"])
t = dispute["disputed_transactions"][0]
print("seller_transaction_id:", t.get("seller_transaction_id"))

txn = get_transaction(t.get("seller_transaction_id"))
print(json.dumps(txn, indent=2)[:3000])