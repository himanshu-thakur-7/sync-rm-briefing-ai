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


def delete(path: str) -> None:
    with httpx.Client(timeout=20) as c:
        r = c.delete(f"{BASE}{path}", params={"api_token": TOKEN})
        if r.status_code >= 400:
            try: body = r.json()
            except Exception: body = r.text
            raise RuntimeError(f"DELETE {path} HTTP {r.status_code}: {body}")


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
    {"name": "Date of Birth", "field_type": "date"},
    {"name": "City", "field_type": "varchar"},
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
    # Vikram is the demo's high-risk client — point his number at the
    # presenter's phone so the autonomous save call rings during the demo.
    "client_005": "+917678456033",
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


# ── 2a. Organizations — needed because Pipedrive stores company on a related
# Organization entity, not directly on Person. Without this the briefing reads
# "Vikram, Managing Director at  in  " — empty company + city. Find-or-create
# by name (Pipedrive de-dupes by exact name match).

def find_or_create_org(name: str, address: str = "") -> str | None:
    if not name:
        return None
    try:
        r = get("/organizations/search", params={"term": name, "fields": "name", "exact_match": True, "limit": 5})
        items = ((r.get("data") or {}).get("items") or []) if isinstance(r, dict) else []
        for it in items:
            obj = it.get("item") if isinstance(it, dict) else None
            if obj and obj.get("id"):
                return str(obj["id"])
    except Exception:
        pass
    try:
        body = {"name": name}
        if address:
            body["address"] = address
        res = post("/organizations", body)
        return str((res.get("data") or {}).get("id", ""))
    except Exception as e:
        print(f"  ! org create {name}: {e}")
        return None


# Address strings give the org a realistic location (helps SYNC's briefing read
# "Senior Manager at Infosys in Bengaluru" instead of just "Senior Manager at Infosys").
ORG_ADDRESSES = {
    "Infosys":                 "Electronic City, Bengaluru, KA 560100, India",
    "Unilever":                "Andheri East, Mumbai, MH 400099, India",
    "Kulkarni Textiles":       "Kalbadevi, Pune, MH 411011, India",
    "Google":                  "Outer Ring Road, Hyderabad, TS 500032, India",
    "Desai Infrastructure Ltd":"Bodakdev, Ahmedabad, GJ 380054, India",
}


print("\n[2a/4] Creating Organizations…")
org_ids: dict[str, str] = {}  # company name → org id
for cid, full in database.CLIENTS.items():
    company = full.profile.company
    if company and company not in org_ids:
        oid = find_or_create_org(company, ORG_ADDRESSES.get(company, ""))
        if oid:
            org_ids[company] = oid
            print(f"  + {company} (id={oid})")
        time.sleep(0.15)


print("\n[2b/4] Upserting 5 demo Persons (with Organization, DOB, City)…")
person_ids: dict[str, str] = {}


def wipe_person_artifacts(pid: int) -> None:
    """Delete all Deals and Activities linked to a Person so re-running the
    seeder doesn't accumulate duplicates."""
    # Deals
    try:
        d = get(f"/persons/{pid}/deals", params={"status": "all_not_deleted", "limit": 200})
        for deal in (d.get("data") or []) or []:
            if deal and deal.get("id"):
                try: delete(f"/deals/{deal['id']}")
                except Exception: pass
    except Exception:
        pass
    # Activities
    try:
        d = get(f"/persons/{pid}/activities", params={"limit": 200})
        for a in (d.get("data") or []) or []:
            if a and a.get("id"):
                try: delete(f"/activities/{a['id']}")
                except Exception: pass
    except Exception:
        pass

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
    # Derive a plausible DOB from the in-memory profile's age.
    dob = (date.today() - timedelta(days=p.age * 365 + 90)).isoformat() if p.age else None

    props = {
        "name": p.name,
        "first_name": first,
        "last_name": last,
        "email": [{"label": "work", "value": email, "primary": True}],
        "phone": [{"label": "work", "value": phone, "primary": True}],
        "job_title": p.occupation,
    }
    # Link to Organization → makes `org_name` resolve in the adapter
    oid = org_ids.get(p.company)
    if oid:
        props["org_id"] = int(oid)
    # Custom fields keyed by 40-char hash
    if dob and person_keys.get("Date of Birth"):
        props[person_keys["Date of Birth"]] = dob
    if p.city and person_keys.get("City"):
        props[person_keys["City"]] = p.city
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


# ── 2c. Wipe existing Deals + Activities per demo Person so re-running the
# seeder produces a clean, deterministic state (no duplicate loans/complaints).
print("\n[2c/4] Clearing prior demo Deals + Activities for these Persons…")
for cid, pid in person_ids.items():
    if pid:
        try:
            wipe_person_artifacts(int(pid))
            print(f"  ⌫ cleared {database.CLIENTS[cid].profile.name}")
        except Exception as e:
            print(f"  ! wipe {database.CLIENTS[cid].profile.name}: {e}")
        time.sleep(0.1)


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

    # Past interactions — one row per Interaction in database.py. Gives SYNC's
    # adapter a believable conversation trail per client (not just a synthetic
    # baseline).
    for inter in full.interactions:
        kind = inter.channel.lower()
        type_map = {"phone": "call", "email": "email", "branch": "meeting", "app": "task", "meeting": "meeting"}
        a_type = type_map.get(kind, "call")
        try:
            post("/activities", {
                "subject": f"{a_type.title()} with {full.profile.name}",
                "type": a_type,
                "person_id": int(pid),
                "due_date": inter.date,
                "done": 1,
                "note": inter.summary,
            })
            print(f"  + past {a_type} ({inter.date}) → {full.profile.name}")
        except Exception as e:
            print(f"  ! past activity {full.profile.name}: {e}")
        time.sleep(0.12)


# ── 4b. Upcoming meetings — populates the Morning Brief agenda with real
# pending work. Each client gets one upcoming meeting tied to their storyline.

UPCOMING = {
    "client_001": (2, "meeting",
                    "Home renovation discussion — Rahul mentioned planning a renovation in Q3. "
                    "Walk through Home Improvement Loan rates and Personal Loan top-up."),
    "client_002": (5, "meeting",
                    "Home loan walkthrough — Priya has been house-hunting in Powai for 6 months. "
                    "Bring CIBIL printout + dual-income joint application paperwork."),
    "client_003": (1, "meeting",
                    "URGENT: Loan restructuring discussion — Amit's restructuring request is 20 days "
                    "old and escalated. Bring credit team's response + WC OD pre-approval."),
    "client_004": (3, "call",
                    "Home loan eligibility callback — Sneha spent 8 minutes on the calculator. "
                    "Get her on the phone before another bank does. Lead with the EMI vs. rent angle."),
    "client_005": (1, "call",
                    "URGENT: Payment plan call — Vikram's CC at 92%, 2 missed EMIs. Pitch CC-to-PL "
                    "transfer (saves ~₹3L interest this year). NPA risk in 45 days if pattern continues."),
}

print("\n[4b/4] Creating upcoming meetings (Morning Brief agenda)…")
for cid, full in database.CLIENTS.items():
    pid = person_ids.get(cid)
    if not pid or cid not in UPCOMING:
        continue
    days_ahead, kind, note = UPCOMING[cid]
    when = (today + timedelta(days=days_ahead)).isoformat()
    subj = f"{'URGENT — ' if 'URGENT' in note else ''}{kind.title()} with {full.profile.name}"
    try:
        post("/activities", {
            "subject": subj,
            "type": kind,
            "person_id": int(pid),
            "due_date": when,
            "due_time": "10:00",
            "duration": "00:30",
            "done": 0,
            "note": note,
        })
        print(f"  + upcoming {kind} (+{days_ahead}d) → {full.profile.name}")
    except Exception as e:
        print(f"  ! upcoming for {full.profile.name}: {e}")
    time.sleep(0.15)


print("\n──────────────────────────────────────────────────────────────────────")
print(f"✓ Done. Open https://{DOMAIN}.pipedrive.com/persons/list")
print("  to see Rahul, Priya, Amit, Sneha, Vikram with their Deals + Activities.")
print("\nDemo storyline summary:")
print("  ★ Vikram Desai (HIGH risk)   — CC 92% maxed, NPA risk in 45 days")
print("  • Amit Kulkarni (WATCH risk) — restructuring escalated 20 days ago")
print("  • Rahul Mehta  (LOW risk)    — clean record, daughter education SIP hook")
print("  • Priya Sharma (VERY LOW)    — house-hunting, FD matures soon")
print("  • Sneha Reddy  (VERY LOW)    — Google ESOP, home loan calculator open 5d ago")
print("\nNext steps:")
print(f"  1. .env already has PIPEDRIVE_API_TOKEN + PIPEDRIVE_COMPANY_DOMAIN={DOMAIN}")
print("  2. Restart the backend (rm sync.db so the seed re-runs):")
print("       cd artifacts/sync-backend && rm sync.db && uvicorn main:app --reload")
print("  3. In the dashboard, source switcher should land on Pipedrive automatically.")
