def build_real_evidence(dispute, txn_detail):
    dt = (dispute.get("disputed_transactions") or [{}])[0]
    txn_detail = txn_detail or {}
    if "error" in txn_detail:
        return {"note": "PayPal transaction record unavailable: " + txn_detail["error"]}

    info = txn_detail.get("transaction_info", {})
    ship = txn_detail.get("shipping_info", {})
    buyer_msgs = [
        m.get("content")
        for m in dispute.get("messages", [])
        if m.get("posted_by") == "BUYER"
    ]
    return {
        "paypal_transaction": {
            "transaction_id": info.get("transaction_id"),
            "date": info.get("transaction_initiation_date"),
            "status": info.get("transaction_status"),
            "amount": info.get("transaction_amount"),
        },
        "buyer_name": (dt.get("buyer") or {}).get("name"),
        "shipping_address_on_file": ship.get("address"),
        "buyer_complaint_messages": buyer_msgs,
        "seller_protection_eligible": dt.get("seller_protection_eligible"),
    }