import json
from paypal_client import list_disputes, get_dispute

disputes = list_disputes()

if not disputes:
    print("No disputes found. Check your keys belong to the US Business app.")
else:
    print(f"Found {len(disputes)} dispute(s):\n")
    for d in disputes:
        amount = d.get("dispute_amount", {})
        print("ID:", d.get("dispute_id"))
        print("Reason:", d.get("reason"))
        print("Status:", d.get("status"))
        print("Stage:", d.get("dispute_life_cycle_stage"))
        print("Amount:", amount.get("value"), amount.get("currency_code"))
        print()

    first_id = disputes[0]["dispute_id"]
    print(json.dumps(get_dispute(first_id), indent=2))