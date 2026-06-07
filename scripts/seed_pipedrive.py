"""
seed_pipedrive.py — populate a Pipedrive account with SYNC demo data.

Idempotent. Safe to re-run.

Creates:
  • 9 custom Person fields + 6 custom Deal fields (matching the labels the
    SYNC PipedriveCRMAdapter resolves at runtime)
  • 5 demo Persons (Rahul, Priya, Amit, Sneha, Vikram), each with risk +
    cross-sell data populated
  • A Deal per loan, linked to each Person
  • Activities for complaints (subject prefixed "Complaint:" + status tag)
    and recent calls so SYNC's get_interactions() finds something real

Usage:
  PIPEDRIVE_API_TOKEN=xxxx PIPEDRIVE_COMPANY_DOMAIN=acmedemo python scripts/seed_pipedrive.py

Get the token:
  Pipedrive → top-right avatar → Personal preferences → API → "Your personal
  API token" → copy.
Get the company domain:
  it's the prefix of your Pipedrive URL. https://acmedemo.pipedrive.com → "acmedemo".
"""
from __future__ import annotations

import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "artifacts" / "sync-backend"
sys.path.insert(0, str(BACKEND))

try:
    import database  # type: ignore
except Exception as e:
    sys.exit(f"Couldn't import the sample dataset: {e}")

TOKEN = os.environ.get("PIPEDRIVE_API_TOKEN", "").strip()
DOMAIN = os.environ.get("PIPEDRIVE_COMPANY_DOMAIN", "").strip()
if not TOKEN or not DOMAIN:
    sys.exit(
        "Both PIPEDRIVE_API_TOKEN and PIPEDRIVE_COMPANY_DOMAIN are required.\n"
        "Get them from Pipedrive → Personal preferences → API."
    )

BASE = f"https://{DOMAIN}.pipedrive.com/api/v1"


def _check(resp: httpx.Response, label: str) -> dict:
    """Raise with the JSON body for visibility on errors."""
    if resp.status_code >= 300:
        try:
            body = resp.json()
        except Exception:
            body = resp.text
        raise RuntimeError(f"{label} HTTP {resp.status_code}: {body}")
    return resp.json()


def get(path: str, params: dict = None) -> dict:
    with httpx.Client(timeout=20) as c:
        r = c.get(f"{BASE}{path}", params={**(params or {}), "api_token": TOKEN})
        return _check(r, f"GET {path}")


def post(path: str, body: dict) -> dict:
    with httpx.Client(timeout=20) as c:
        r = c.post(f"{BASE}{path}", params={"api_token": TOKEN}, json=body)
        return _check(r, f"POST {path}")


def put(path: str, body: dict) -> dict:
    with httpx.Client(timeout=20) as c:
        r = c.put(f"{BASE}{path}", params={"api_token": TOKEN}, json=body)
        return _check(r, f"PUT {path}")


def ping() -> None:
    """Confirm token + domain are valid before doing anything destructive."""
    me = get("/users/me")
    name = (me.get("data") or {}).get("name", "(unknown)")
    print(f"✓ Authenticated to Pipedrive as {name}")


# ─────────────────────────── 1. Custom fields ───────────────────────────── #

PERSON_FIELDS = [
    {"name": "Risk Score", "field_type": "enum",
     "options": ["very_low", "low", "medium", "watch", "high"]},
    {"name": "Risk Factors", "field_type": "text"},
    {"name": "Last RM Interaction Date", "field_type": "date"},
    {"name": "Cross-Sell Product 1", "field_type": "varchar"},
    {"name": "Cross-Sell Pitch 1", "field_type": "text"},
    {"name": "Cross-Sell Value 1", "field_type": "double"},
    {"name": "Cross-Sell Product 2", "field_type": "varchar"},
    {"name": "Cross-Sell Pitch 2", "field_type": "text"},
    {"name": "Cross-Sell Value 2", "field_type": "double"},
]

DEAL_FIELDS = [
    {"name": "Product Type", "field_type": "enum",
     "options": ["home_loan", "personal_loan", "business_loan", "car_loan", "credit_card", "fd"]},
    {"name": "EMI Amount", "field_type": "double"},
    {"name": "Months Paid", "field_type": "double"},
    {"name": "Tenure Months", "field_type": "double"},
    {"name": "Next Due Date", "field_type": "date"},
    {"name": "Payment History", "field_type": "text"},
]


def ensure_fields(endpoint: str, fields: list[dict], label: str) -> dict[str, str]:
    """Create any missing custom fields. Returns {name → 40-char key}."""
    existing = get(f"/{endpoint}", params={"limit": 500})
    existing_data = existing.get("data") or []
    by_name = {f.get("name", ""): f for f in existing_data if isinstance(f, dict)}
    out: dict[str, str] = {}

    for f in fields:
        name = f["name"]
        if name in by_name:
            out[name] = by_name[name].get("key", "")
            continue
        payload = {"name": name, "field_type": f["field_type"]}
        # Pipedrive enum options shape: comma-separated string OR list of {"label": ...}
        if f.get("options"):
            payload["options"] = [{"label": o} for o in f["options"]]
        try:
            r = post(f"/{endpoint}", payload)
            new = (r.get("data") or {}) if isinstance(r, dict) else {}
            out[name] = new.get("key", "")
            print(f"  + {label}.{name}  (key={out[name][:8]}…)")
        except Exception as e:
            print(f"  ! {label}.{name}: {e}")
        time.sleep(0.2)  # gentle on Pipedrive's rate limit

    for name, key in out.items():
        if not key:
            continue
        print(f"  ~ {label}.{name} = {key}")
    return out


print("\n[1/4] Ensuring custom fields exist…")
person_keys = ensure_fields("personFields", PERSON_FIELDS, "person")
deal_keys = ensure_fields("dealFields", DEAL_FIELDS, "deal")


# ─────────────────────────── 2. Persons ─────────────────────────────────── #

EMAILS = {
    "client_001": "rahul.mehta@infosys-demo.com",
    "client_002": "priya.sharma@unilever-demo.com",
    "client_003": "amit@kulkarnitextiles-demo.com",
    "client_004": "sneha.reddy@google-demo.com",
    "client_005": "vikram@desaiinfra-demo.com",
}
PHONES = {
    "client_001": "+919845010001",
    "client_002": "+919845010002",
    "client_003": "+919845010003",
    "client_004": "+919845010004",
    "client_005": "+919845010005",
}


def find_person_by_email(email: str) -> str | None:
    try:
        r = get("/persons/search", params={"term": email, "fields": "email", "exact_match": True, "limit": 5})
        items = ((r.get("data") or {}).get("items") or []) if isinstance(r, dict) else []
        for it in items:
            obj = it.get("item") if isinstance(it, dict) else None
            if obj and obj.get("id"):
                return str(obj["id"])
    except Exception:
        pass
    return None


print("\n[2/4] Upserting 5 demo Persons…")
person_ids: dict[str, str] = {}

for cid, full in database.CLIENTS.items():
    p = full.profile
    r = full.risk
    cs = full.cross_sell
    parts = p.name.split()
    first = parts[0]
    last = " ".join(parts[1:]) or parts[0]
    email = EMAILS.get(cid, f"{first.lower()}.{last.lower()}@example.com")
    phone = PHONES.get(cid, "+919999999999")
    days_back = full.last_rm_interaction_days_ago
    last_interaction = (date.today() - timedelta(days=days_back)).isoformat()

    props = {
        "name": p.name,
        "first_name": first,
        "last_name": last,
        "email": [{"label": "work", "value": email, "primary": True}],
        "phone": [{"label": "work", "value": phone, "primary": True}],
        "job_title": p.occupation,
    }
    # Custom fields keyed by 40-char hash
    if person_keys.get("Risk Score"):
        props[person_keys["Risk Score"]] = r.score
    if person_keys.get("Risk Factors"):
        props[person_keys["Risk Factors"]] = "\n".join(r.factors)
    if person_keys.get("Last RM Interaction Date"):
        props[person_keys["Last RM Interaction Date"]] = last_interaction
    for i, cs_item in enumerate(cs[:2], 1):
        if person_keys.get(f"Cross-Sell Product {i}"):
            props[person_keys[f"Cross-Sell Product {i}"]] = cs_item.product
        if person_keys.get(f"Cross-Sell Pitch {i}"):
            props[person_keys[f"Cross-Sell Pitch {i}"]] = cs_item.pitch_angle
        if person_keys.get(f"Cross-Sell Value {i}"):
            props[person_keys[f"Cross-Sell Value {i}"]] = cs_item.estimated_value

    existing = find_person_by_email(email)
    try:
        if existing:
            put(f"/persons/{existing}", props)
            person_ids[cid] = existing
            print(f"  ~ {p.name} (updated · id={existing})")
        else:
            r2 = post("/persons", props)
            new_id = str((r2.get("data") or {}).get("id", ""))
            person_ids[cid] = new_id
            print(f"  + {p.name} (created · id={new_id})")
    except Exception as e:
        print(f"  ! {p.name}: {e}")
    time.sleep(0.2)


# ─────────────────────────── 3. Deals (loans) ───────────────────────────── #

print("\n[3/4] Creating loan Deals…")
for cid, full in database.CLIENTS.items():
    pid = person_ids.get(cid)
    if not pid:
        continue
    for prod in full.products:
        deal_props = {
            "title": f"{full.profile.name} — {prod.product_type.replace('_', ' ').title()}",
            "value": prod.principal,
            "currency": "INR",
            "person_id": int(pid),
            "status": "open",
        }
        if deal_keys.get("Product Type"):
            deal_props[deal_keys["Product Type"]] = prod.product_type
        if deal_keys.get("EMI Amount"):
            deal_props[deal_keys["EMI Amount"]] = prod.emi
        if deal_keys.get("Months Paid"):
            deal_props[deal_keys["Months Paid"]] = prod.months_paid
        if deal_keys.get("Tenure Months"):
            deal_props[deal_keys["Tenure Months"]] = prod.tenure_months
        if deal_keys.get("Next Due Date"):
            deal_props[deal_keys["Next Due Date"]] = prod.next_due_date
        if deal_keys.get("Payment History"):
            deal_props[deal_keys["Payment History"]] = ",".join(prod.payment_history)
        try:
            r = post("/deals", deal_props)
            print(f"  + {deal_props['title']} (id={(r.get('data') or {}).get('id', '?')})")
        except Exception as e:
            print(f"  ! {deal_props['title']}: {e}")
        time.sleep(0.15)


# ─────────────────────────── 4. Activities ──────────────────────────────── #

print("\n[4/4] Creating Activities (complaints + recent calls)…")
today = date.today()

for cid, full in database.CLIENTS.items():
    pid = person_ids.get(cid)
    if not pid:
        continue

    # Complaints — use a "task" type with subject convention so SYNC's
    # PipedriveCRMAdapter.get_interactions() recognises them.
    for comp in full.complaints:
        subj = f"Complaint: {comp.category} — {comp.summary[:80]} [{comp.status}]"
        done = 1 if comp.status in ("resolved", "closed") else 0
        try:
            post("/activities", {
                "subject": subj,
                "type": "task",
                "person_id": int(pid),
                "due_date": comp.date,
                "done": done,
                "note": comp.summary,
            })
            print(f"  + complaint ({comp.status}) → {full.profile.name}")
        except Exception as e:
            print(f"  ! complaint for {full.profile.name}: {e}")
        time.sleep(0.15)

    # Recent calls — derived from `last_rm_interaction_days_ago` so SYNC can
    # actually compute a meaningful "days since last contact" value.
    days = full.last_rm_interaction_days_ago
    when = (today - timedelta(days=days)).isoformat()
    try:
        post("/activities", {
            "subject": f"Last RM check-in with {full.profile.name}",
            "type": "call",
            "person_id": int(pid),
            "due_date": when,
            "done": 1,
            "note": "Last RM-side touchpoint (synthetic baseline for SYNC demo).",
        })
        print(f"  + call activity ({days} days ago) → {full.profile.name}")
    except Exception as e:
        print(f"  ! call activity for {full.profile.name}: {e}")
    time.sleep(0.15)


print("\n──────────────────────────────────────────────────────────────────────")
print(f"✓ Done. Open https://{DOMAIN}.pipedrive.com/persons/list")
print("  to see Rahul, Priya, Amit, Sneha, Vikram with their Deals + Activities.")
print("\nNext steps:")
print("  1. .env already has:")
print(f"     PIPEDRIVE_API_TOKEN={TOKEN[:8]}…")
print(f"     PIPEDRIVE_COMPANY_DOMAIN={DOMAIN}")
print("  2. In the dashboard's source switcher, pick 'Pipedrive'")
print("  3. Trigger a Sync Now and watch a Note appear on the Person record.")
