# Fake store records, as if from the merchant's own system.
# Key = PayPal transaction ID of the payment.

ORDERS = {
    "31T82654EC2117430": {
        "order_id": "ORD-1001",
        "item": "Running shoes",
        "amount_usd": 10.00,
        "ordered_on": "2026-10-25",
        "shipped_on": "2026-10-26",
        "courier": "BlueDart",
        "tracking_number": "BD123456789IN",
        "tracking_status": "DELIVERED",
        "delivered_on": "2026-10-29",
        "delivery_proof": "Signed by 'A. Gunjal' at front door, photo on file",
        "customer_messages": [
            "2026-10-30: Customer asked 'Where is my order?'",
            "2026-10-30: Store replied with tracking link and delivery photo",
        ],
    }
}


def get_evidence(transaction_id):
    return ORDERS.get(transaction_id)