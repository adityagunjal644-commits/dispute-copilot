from datetime import datetime, timedelta, timezone


def _due(days):
    return (datetime.now(timezone.utc) + timedelta(days=days)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _d(dispute_id, reason, amount, created, txn, due_days):
    return {
        "dispute_id": dispute_id,
        "reason": reason,
        "status": "WAITING_FOR_SELLER_RESPONSE",
        "dispute_life_cycle_stage": "INQUIRY",
        "dispute_amount": {"value": amount, "currency_code": "USD"},
        "create_time": created,
        "seller_response_due_date": _due(due_days),
        "disputed_transactions": [{"buyer_transaction_id": txn}],
    }


DEMO_DISPUTES = [
    _d("DEMO-1001", "MERCHANDISE_OR_SERVICE_NOT_RECEIVED", "48.00", "2026-10-28T10:00:00Z", "DEMO-TXN-1", 9),
    _d("DEMO-1002", "MERCHANDISE_OR_SERVICE_NOT_RECEIVED", "120.00", "2026-10-29T09:30:00Z", "DEMO-TXN-2", 1),
    _d("DEMO-1003", "MERCHANDISE_OR_SERVICE_NOT_AS_DESCRIBED", "75.50", "2026-10-30T14:15:00Z", "DEMO-TXN-3", 4),
    _d("DEMO-1004", "UNAUTHORISED", "260.00", "2026-10-30T18:45:00Z", "DEMO-TXN-4", 2),
    _d("DEMO-1005", "MERCHANDISE_OR_SERVICE_NOT_RECEIVED", "32.00", "2026-10-31T07:20:00Z", "DEMO-TXN-5", 6),
    _d("DEMO-1006", "MERCHANDISE_OR_SERVICE_NOT_RECEIVED", "89.00", "2026-10-22T11:00:00Z", "DEMO-TXN-6", 5),
]

DEMO_EVIDENCE = {
    "DEMO-TXN-1": {
        "item": "Wireless earbuds", "ordered_on": "2026-10-20", "shipped_on": "2026-10-21",
        "courier": "Delhivery", "tracking_number": "DL998877", "tracking_status": "DELIVERED",
        "delivered_on": "2026-10-24", "delivery_proof": "OTP-verified delivery, GPS match to buyer address",
        "customer_messages": ["2026-10-27: Buyer asked where the order is; store replied with OTP delivery proof"],
    },
    "DEMO-TXN-2": {
        "item": "Smart watch", "ordered_on": "2026-10-15", "shipped_on": "2026-10-16",
        "courier": "BlueDart", "tracking_number": "BD554433", "tracking_status": "IN_TRANSIT",
        "delivered_on": None, "delivery_proof": None,
        "customer_messages": ["2026-10-28: Buyer says nothing arrived after 13 days", "No reply sent yet by store"],
    },
    "DEMO-TXN-3": {
        "item": "Leather laptop bag", "ordered_on": "2026-10-22", "shipped_on": "2026-10-23",
        "courier": "DTDC", "tracking_number": "DT221100", "tracking_status": "DELIVERED",
        "delivered_on": "2026-10-26", "delivery_proof": "Left with security guard",
        "listing_description": "Genuine leather",
        "customer_messages": ["2026-10-29: Buyer sent photos showing faux leather and a torn strap"],
    },
    "DEMO-TXN-4": None,
    "DEMO-TXN-5": {
        "item": "Phone case", "ordered_on": "2026-10-25", "shipped_on": "2026-10-26",
        "courier": "India Post", "tracking_number": "IP778899", "tracking_status": "DELIVERED",
        "delivered_on": "2026-10-29", "delivery_proof": "Delivered to neighbour, signature unreadable",
        "customer_messages": ["2026-10-30: Buyer says they never saw the parcel"],
    },
    "DEMO-TXN-6": {
        "item": "Gaming keyboard", "ordered_on": "2026-10-18", "shipped_on": "2026-10-19",
        "courier": "Ecom Express", "tracking_number": "EE445566", "tracking_status": "DELIVERED",
        "delivered_on": "2026-10-23", "delivery_proof": "Left at front desk, signature unreadable",
        "courier_tracking": {"status": "DELIVERED", "delivered_on": "2026-10-26", "tracking_number": "EE445566"},
        "customer_messages": ["2026-10-22: Buyer says nothing has arrived"],
    },
}