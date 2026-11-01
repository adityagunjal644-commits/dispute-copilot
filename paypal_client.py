import os
import requests
from dotenv import load_dotenv

load_dotenv()

BASE_URL = "https://api-m.sandbox.paypal.com"
CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")


def get_access_token():
    if not CLIENT_ID or not CLIENT_SECRET:
        raise SystemExit("Missing keys in .env file")
    r = requests.post(
        f"{BASE_URL}/v1/oauth2/token",
        auth=(CLIENT_ID, CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    if r.status_code != 200:
        raise SystemExit(f"Login failed ({r.status_code}): {r.text}")
    return r.json()["access_token"]


def headers():
    return {
        "Authorization": f"Bearer {get_access_token()}",
        "Content-Type": "application/json",
    }


def list_disputes():
    r = requests.get(f"{BASE_URL}/v1/customer/disputes", headers=headers(), timeout=30)
    if r.status_code != 200:
        raise SystemExit(f"Could not list disputes ({r.status_code}): {r.text}")
    return r.json().get("items", [])


def get_dispute(dispute_id):
    r = requests.get(
        f"{BASE_URL}/v1/customer/disputes/{dispute_id}", headers=headers(), timeout=30
    )
    if r.status_code != 200:
        raise SystemExit(f"Could not get dispute ({r.status_code}): {r.text}")
    return r.json()

def send_message(dispute_id, message):
    r = requests.post(
        f"{BASE_URL}/v1/customer/disputes/{dispute_id}/send-message",
        headers=headers(),
        json={"message": message},
        timeout=30,
    )
    if r.status_code not in (200, 202):
        raise SystemExit(f"Could not send message ({r.status_code}): {r.text}")
    return r.json()

from datetime import datetime, timedelta, timezone


def get_transaction(transaction_id, days_back=30):
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=days_back)
    fmt = "%Y-%m-%dT%H:%M:%S-0000"
    params = {
        "transaction_id": transaction_id,
        "start_date": start.strftime(fmt),
        "end_date": end.strftime(fmt),
        "fields": "all",
    }
    r = requests.get(
        f"{BASE_URL}/v1/reporting/transactions",
        headers=headers(),
        params=params,
        timeout=30,
    )
    if r.status_code != 200:
        return {"error": f"{r.status_code}: {r.text[:200]}"}
    details = r.json().get("transaction_details", [])
    return details[0] if details else {"error": "Transaction not found yet"}

def add_tracking(transaction_id, tracking_number, carrier_name, status="DELIVERED"):
    body = {
        "trackers": [{
            "transaction_id": transaction_id,
            "tracking_number": tracking_number,
            "status": status,
            "carrier": "OTHER",
            "carrier_name_other": carrier_name,
        }]
    }
    r = requests.post(
        f"{BASE_URL}/v1/shipping/trackers-batch",
        headers=headers(),
        json=body,
        timeout=30,
    )
    return r.status_code, r.text[:1500]


def get_tracking(transaction_id, tracking_number):
    r = requests.get(
        f"{BASE_URL}/v1/shipping/trackers/{transaction_id}-{tracking_number}",
        headers=headers(),
        timeout=30,
    )
    if r.status_code != 200:
        return {"error": f"{r.status_code}: {r.text[:200]}"}
    return r.json()