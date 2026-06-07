"""
seed_hubspot.py — populate a HubSpot account with SYNC demo data.

Idempotent. Safe to re-run.

Creates:
  • 9 custom Contact properties (risk_score, risk_factors, last_rm_interaction_date,
    cross_sell_product_1/2, cross_sell_pitch_1/2, cross_sell_value_1/2)
  • 6 custom Deal properties (product_type, emi_amount, months_paid,
    tenure_months, next_due_date, payment_history)
  • 5 demo Contacts (Rahul Mehta, Priya Sharma, Amit Kulkarni, Sneha Reddy,
    Vikram Desai), each with full risk + cross-sell data
  • Loan Deals linked to each contact
  • Complaint Tickets linked to contacts that have open complaints

Usage:
  HUBSPOT_ACCESS_TOKEN=pat-na1-xxxxxxxx python scripts/seed_hubspot.py

To get the token: HubSpot → Settings (gear icon) → Integrations → Private Apps
→ Create a private app → grant the scopes listed in HUBSPOT_RINGG_SETUP.md
→ copy the "Access token".
"""
from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "artifacts" / "sync-backend"
sys.path.insert(0, str(BACKEND))

try:
    import database  # type: ignore
except Exception as e:
    sys.exit(f"Couldn't import the sample dataset: {e}")

try:
    from hubspot import HubSpot
    from hubspot.crm.contacts import (
        PublicObjectSearchRequest as ContactSearch,
        Filter as ContactFilter,
        FilterGroup as ContactFilterGroup,
        SimplePublicObjectInputForCreate as ContactCreate,
        SimplePublicObjectInput as ContactUpdate,
    )
    from hubspot.crm.deals import SimplePublicObjectInputForCreate as DealCreate
    from hubspot.crm.tickets import SimplePublicObjectInputForCreate as TicketCreate
    from hubspot.crm.properties import PropertyCreate, PropertyGroupCreate
except ImportError:
    sys.exit("hubspot-api-client not installed. Run: pip install hubspot-api-client")


TOKEN = (
    os.environ.get("HUBSPOT_ACCESS_TOKEN")
    or os.environ.get("HUBSPOT_API_KEY")
    or ""
)
if not TOKEN:
    sys.exit(
        "Set HUBSPOT_ACCESS_TOKEN (or HUBSPOT_API_KEY) to your HubSpot Private App "
        "access token, then re-run."
    )

hs = HubSpot(access_token=TOKEN)
print("✓ Authenticated to HubSpot")


# ──────────────────────── 1. Custom properties ───────────────────────── #

CONTACT_PROPS = [
    {"name": "risk_score", "label": "Risk Score", "type": "enumeration",
     "field_type": "select",
     "options": ["very_low", "low", "medium", "watch", "high"]},
    {"name": "risk_factors", "label": "Risk Factors", "type": "string",
     "field_type": "textarea"},
    {"name": "last_rm_interaction_date", "label": "Last RM Interaction Date",
     "type": "date", "field_type": "date"},
    {"name": "cross_sell_product_1", "label": "Cross-Sell Product 1",
     "type": "string", "field_type": "text"},
    {"name": "cross_sell_pitch_1", "label": "Cross-Sell Pitch 1",
     "type": "string", "field_type": "textarea"},
    {"name": "cross_sell_value_1", "label": "Cross-Sell Value 1",
     "type": "number", "field_type": "number"},
    {"name": "cross_sell_product_2", "label": "Cross-Sell Product 2",
     "type": "string", "field_type": "text"},
    {"name": "cross_sell_pitch_2", "label": "Cross-Sell Pitch 2",
     "type": "string", "field_type": "textarea"},
    {"name": "cross_sell_value_2", "label": "Cross-Sell Value 2",
     "type": "number", "field_type": "number"},
]

DEAL_PROPS = [
    {"name": "product_type", "label": "Product Type", "type": "enumeration",
     "field_type": "select",
     "options": ["home_loan", "personal_loan", "business_loan", "car_loan",
                 "credit_card", "fd"]},
    {"name": "emi_amount", "label": "EMI Amount", "type": "number",
     "field_type": "number"},
    {"name": "months_paid", "label": "Months Paid", "type": "number",
     "field_type": "number"},
    {"name": "tenure_months", "label": "Tenure (Months)", "type": "number",
     "field_type": "number"},
    {"name": "next_due_date", "label": "Next Due Date", "type": "date",
     "field_type": "date"},
    {"name": "payment_history", "label": "Payment History", "type": "string",
     "field_type": "textarea"},
]

GROUP_NAME = "sync_rm_briefing"
GROUP_LABEL = "SYNC RM Briefing"


def _is_already_exists(err: Exception) -> bool:
    s = str(err).lower()
    return "already exists" in s or "duplicate" in s or "is already used" in s


def ensure_group(object_type: str) -> None:
    try:
        hs.crm.properties.groups_api.create(
            object_type=object_type,
            property_group_create=PropertyGroupCreate(
                name=GROUP_NAME, display_order=-1, label=GROUP_LABEL,
            ),
        )
        print(f"  + group '{GROUP_NAME}' on {object_type}")
    except Exception as e:
        if _is_already_exists(e):
            return
        print(f"  ! group on {object_type}: {e}")


def ensure_props(object_type: str, props: list[dict]) -> None:
    for p in props:
        try:
            hs.crm.properties.core_api.create(
                object_type=object_type,
                property_create=PropertyCreate(
                    name=p["name"], label=p["label"], type=p["type"],
                    field_type=p["field_type"], group_name=GROUP_NAME,
                    options=[{"label": o, "value": o, "displayOrder": i}
                             for i, o in enumerate(p.get("options", []))],
                ),
            )
            print(f"  + {p['name']} on {object_type}")
        except Exception as e:
            if _is_already_exists(e):
                continue
            print(f"  ! {p['name']} on {object_type}: {e}")


print("\n[1/4] Ensuring custom properties exist…")
ensure_group("contacts")
ensure_group("deals")
ensure_props("contacts", CONTACT_PROPS)
ensure_props("deals", DEAL_PROPS)


# ──────────────────────── 2. Contacts ──────────────────────────────────── #

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


def find_contact_by_email(email: str) -> str | None:
    try:
        req = ContactSearch(
            filter_groups=[ContactFilterGroup(filters=[
                ContactFilter(property_name="email", operator="EQ", value=email),
            ])],
            properties=["email"], limit=1,
        )
        res = hs.crm.contacts.search_api.do_search(public_object_search_request=req)
        return res.results[0].id if res.results else None
    except Exception:
        return None


print("\n[2/4] Upserting 5 demo contacts…")
contact_ids: dict[str, str] = {}

for cid, full in database.CLIENTS.items():
    p = full.profile
    r = full.risk
    cs = full.cross_sell
    parts = p.name.split()
    fname, lname = parts[0], " ".join(parts[1:]) or parts[0]
    email = EMAILS.get(cid, f"{fname.lower()}.{lname.lower()}@example.com")
    phone = PHONES.get(cid, "+919999999999")

    props: dict[str, object] = {
        "firstname": fname,
        "lastname": lname,
        "email": email,
        "phone": phone,
        "jobtitle": p.occupation,
        "company": p.company,
        "city": p.city,
        "risk_score": r.score,
        "risk_factors": "\n".join(r.factors),
        "last_rm_interaction_date": (
            date.today() - timedelta(days=full.last_rm_interaction_days_ago)
        ).isoformat(),
    }
    for i, cs_item in enumerate(cs[:2], 1):
        props[f"cross_sell_product_{i}"] = cs_item.product
        props[f"cross_sell_pitch_{i}"] = cs_item.pitch_angle
        props[f"cross_sell_value_{i}"] = cs_item.estimated_value

    existing = find_contact_by_email(email)
    if existing:
        try:
            hs.crm.contacts.basic_api.update(
                contact_id=existing,
                simple_public_object_input=ContactUpdate(properties=props),
            )
            contact_ids[cid] = existing
            print(f"  ~ {p.name} (updated · id={existing})")
        except Exception as e:
            print(f"  ! update {p.name}: {e}")
    else:
        try:
            res = hs.crm.contacts.basic_api.create(
                simple_public_object_input_for_create=ContactCreate(properties=props),
            )
            contact_ids[cid] = res.id
            print(f"  + {p.name} (created · id={res.id})")
        except Exception as e:
            print(f"  ! create {p.name}: {e}")


# ──────────────────────── 3. Loan deals ────────────────────────────────── #

print("\n[3/4] Creating loan deals…")
for cid, full in database.CLIENTS.items():
    hs_contact_id = contact_ids.get(cid)
    if not hs_contact_id:
        continue
    for prod in full.products:
        deal_name = f"{full.profile.name} — {prod.product_type.replace('_', ' ').title()}"
        deal_props = {
            "dealname": deal_name,
            "amount": str(prod.principal),
            "dealstage": "presentationscheduled",
            "product_type": prod.product_type,
            "emi_amount": prod.emi,
            "months_paid": prod.months_paid,
            "tenure_months": prod.tenure_months,
            "next_due_date": prod.next_due_date,
            "payment_history": ",".join(prod.payment_history),
        }
        try:
            res = hs.crm.deals.basic_api.create(
                simple_public_object_input_for_create=DealCreate(
                    properties=deal_props,
                    associations=[{
                        "to": {"id": hs_contact_id},
                        "types": [{
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 3,  # deal_to_contact
                        }],
                    }],
                ),
            )
            print(f"  + {deal_name} (id={res.id})")
        except Exception as e:
            print(f"  ! {deal_name}: {e}")


# ──────────────────────── 4. Complaint tickets ─────────────────────────── #

print("\n[4/4] Creating complaint tickets…")
for cid, full in database.CLIENTS.items():
    hs_contact_id = contact_ids.get(cid)
    if not hs_contact_id:
        continue
    for comp in full.complaints:
        ticket_props = {
            "subject": f"{comp.category} — {full.profile.name}",
            "content": comp.summary,
            "hs_pipeline": "0",                       # default support pipeline
            "hs_pipeline_stage": "1" if comp.status == "open" else "4",
            "hs_ticket_category": comp.category,
        }
        try:
            res = hs.crm.tickets.basic_api.create(
                simple_public_object_input_for_create=TicketCreate(
                    properties=ticket_props,
                    associations=[{
                        "to": {"id": hs_contact_id},
                        "types": [{
                            "associationCategory": "HUBSPOT_DEFINED",
                            "associationTypeId": 16,  # ticket_to_contact
                        }],
                    }],
                ),
            )
            print(f"  + {comp.category} ({comp.status}) → {full.profile.name} (id={res.id})")
        except Exception as e:
            print(f"  ! {comp.category}: {e}")


print("\n──────────────────────────────────────────────────────────────────────")
print("✓ Done. Open HubSpot → Contacts to see Rahul, Priya, Amit, Sneha, Vikram.")
print("  Each has a Deal (their loan) and — where applicable — a Ticket (complaint).")
print("\nNext steps:")
print("  1. Put your token in .env:     HUBSPOT_API_KEY=<same token>")
print("  2. (Optional) connect via UI:  /settings/integrations → Connect HubSpot")
print("  3. Restart the backend, switch the source switcher to HubSpot in SYNC.")
