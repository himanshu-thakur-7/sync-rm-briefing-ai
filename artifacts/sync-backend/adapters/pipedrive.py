"""Pipedrive CRM adapter — the showcase CRM for the demo.

Auth:
  Personal API token (fast path): query param ?api_token=xxx on every request.
  OAuth 2.0 (production): pass `Authorization: Bearer <token>` and use
    OAuth domain `https://api.pipedrive.com/v1` (no per-tenant subdomain).
  This adapter supports both: with an OAuth token in SecretStore it switches
  to Bearer + the OAuth base; otherwise it uses the personal-token fallback.

API base (personal token): https://{company_domain}.pipedrive.com/api/v1
API base (OAuth):           https://api.pipedrive.com/v1

Resources used:
  - persons        → ClientProfile
  - deals          → LoanProduct (we treat each Deal as one product/loan)
  - activities     → Interaction  (Pipedrive's "call", "meeting", "task" types)
  - notes          → log_briefing writeback
  - personFields   → metadata lookup for custom-field 40-char keys

Custom field naming (matches the seed script):
  Person custom fields (resolved from `personFields` by name):
    Risk Score, Risk Factors, Last RM Interaction Date,
    Cross-Sell Product 1/2, Cross-Sell Pitch 1/2, Cross-Sell Value 1/2
  Deal custom fields:
    Product Type, EMI Amount, Months Paid, Tenure Months, Next Due Date, Payment History

  Pipedrive returns each custom field with a 40-char hex `key` that the
  payload must use (e.g. `a1b2c3...`). We resolve those once and cache.
"""
from __future__ import annotations

import logging
from datetime import date, datetime
from typing import Optional

import httpx
from rapidfuzz import fuzz
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception

from adapters.base import CRMAdapter
from models import (
    BriefingLog, ClientFullProfile, ClientProfile, Complaint,
    CrossSellOpportunity, Interaction, LoanProduct, RiskAssessment,
)

logger = logging.getLogger(__name__)


def _throttled(exc: Exception) -> bool:
    return isinstance(exc, httpx.HTTPStatusError) and exc.response.status_code == 429


# Friendly field names → exposed to the rest of SYNC. The values here are
# the LABELS Pipedrive shows; the adapter resolves these to the 40-char
# `key` at runtime via the /personFields and /dealFields metadata endpoints.
PERSON_FIELD_LABELS = {
    "risk_score": "Risk Score",
    "risk_factors": "Risk Factors",
    "last_rm_interaction_date": "Last RM Interaction Date",
    "date_of_birth": "Date of Birth",
    "city": "City",
    "cross_sell_product_1": "Cross-Sell Product 1",
    "cross_sell_pitch_1": "Cross-Sell Pitch 1",
    "cross_sell_value_1": "Cross-Sell Value 1",
    "cross_sell_product_2": "Cross-Sell Product 2",
    "cross_sell_pitch_2": "Cross-Sell Pitch 2",
    "cross_sell_value_2": "Cross-Sell Value 2",
}
DEAL_FIELD_LABELS = {
    "product_type": "Product Type",
    "emi_amount": "EMI Amount",
    "months_paid": "Months Paid",
    "tenure_months": "Tenure Months",
    "next_due_date": "Next Due Date",
    "payment_history": "Payment History",
}


class PipedriveCRMAdapter(CRMAdapter):
    """Pipedrive REST API adapter (v1)."""

    def __init__(self, *, connection_id: str = "pipedrive_default", metadata: Optional[dict] = None) -> None:
        self._connection_id = connection_id
        self._meta = metadata or {}
        # Caches for the per-tenant 40-char custom-field keys
        self._person_keys: dict[str, str] = {}
        self._deal_keys: dict[str, str] = {}
        # Enum option-id → label maps, keyed by the 40-char custom-field key.
        # Pipedrive enum fields store the option's numeric id on the record,
        # not the human-readable label. We resolve at read time.
        self._person_enum_options: dict[str, dict[str, str]] = {}
        self._deal_enum_options: dict[str, dict[str, str]] = {}

    # ─── HTTP plumbing ───────────────────────────────────────────────────

    async def _auth(self) -> tuple[str, dict, dict]:
        """Return (base_url, query_params, headers) for the current connection.

        Prefers OAuth tokens in SecretStore; falls back to the env-configured
        personal API token + company domain.
        """
        from config import settings
        from services.secret_store import secret_store

        token = await secret_store().get_token(self._connection_id)
        if token and token.get("access_token"):
            # OAuth path — Pipedrive returns a `api_domain` on each connection.
            api_domain = token.get("api_domain") or "https://api.pipedrive.com"
            return f"{api_domain}/v1", {}, {"Authorization": f"Bearer {token['access_token']}"}

        # Personal-token fallback
        company = self._meta.get("company_domain") or settings.pipedrive_company_domain or "api"
        api_token = (token or {}).get("api_token") or settings.pipedrive_api_token
        base = f"https://{company}.pipedrive.com/api/v1"
        return base, {"api_token": api_token}, {}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.6, min=0.6, max=4),
        retry=retry_if_exception(_throttled),
    )
    async def _get(self, path: str, params: Optional[dict] = None) -> dict:
        base, auth_q, headers = await self._auth()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.get(f"{base}{path}", params={**auth_q, **(params or {})}, headers=headers)
            r.raise_for_status()
            return r.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=0.6, min=0.6, max=4),
        retry=retry_if_exception(_throttled),
    )
    async def _post(self, path: str, body: dict) -> dict:
        base, auth_q, headers = await self._auth()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.post(f"{base}{path}", params=auth_q, headers=headers, json=body)
            r.raise_for_status()
            return r.json()

    async def _put(self, path: str, body: dict) -> dict:
        base, auth_q, headers = await self._auth()
        async with httpx.AsyncClient(timeout=20) as c:
            r = await c.put(f"{base}{path}", params=auth_q, headers=headers, json=body)
            r.raise_for_status()
            return r.json()

    # ─── Field-key resolution (cached per adapter instance) ──────────────

    async def _load_person_keys(self) -> dict[str, str]:
        if self._person_keys:
            return self._person_keys
        try:
            data = await self._get("/personFields", params={"limit": 500})
            fields = (data.get("data") or []) if isinstance(data, dict) else []
            label_to_key = {f.get("name", "").lower(): f.get("key", "") for f in fields if f.get("key")}
            for friendly, label in PERSON_FIELD_LABELS.items():
                k = label_to_key.get(label.lower())
                if k:
                    self._person_keys[friendly] = k
            # Cache enum option-id → label maps for every enum field on Person
            for f in fields:
                if f.get("field_type") == "enum" and f.get("key"):
                    opts = {str(o.get("id")): o.get("label", "") for o in (f.get("options") or [])}
                    self._person_enum_options[f["key"]] = opts
        except Exception as e:
            logger.warning("Pipedrive person field metadata load failed: %s", e)
        return self._person_keys

    def _resolve_enum(self, options_map: dict[str, dict[str, str]], key: str, value) -> str:
        """Translate a Pipedrive enum option id back to its label."""
        if value is None or value == "":
            return ""
        opts = options_map.get(key) or {}
        return opts.get(str(value), str(value))

    async def _load_deal_keys(self) -> dict[str, str]:
        if self._deal_keys:
            return self._deal_keys
        try:
            data = await self._get("/dealFields", params={"limit": 500})
            fields = (data.get("data") or []) if isinstance(data, dict) else []
            label_to_key = {f.get("name", "").lower(): f.get("key", "") for f in fields if f.get("key")}
            # Cache enum option-id → label maps for every enum field on Deal
            for f in fields:
                if f.get("field_type") == "enum" and f.get("key"):
                    opts = {str(o.get("id")): o.get("label", "") for o in (f.get("options") or [])}
                    self._deal_enum_options[f["key"]] = opts
            for friendly, label in DEAL_FIELD_LABELS.items():
                k = label_to_key.get(label.lower())
                if k:
                    self._deal_keys[friendly] = k
        except Exception as e:
            logger.warning("Pipedrive deal field metadata load failed: %s", e)
        return self._deal_keys

    # ─── Mapping helpers ─────────────────────────────────────────────────

    async def _person_to_profile(self, p: dict) -> ClientProfile:
        keys = await self._load_person_keys()

        def cf(name: str) -> str:
            key = keys.get(name)
            if not key:
                return ""
            v = p.get(key)
            if isinstance(v, dict):
                return v.get("value") or v.get("name") or ""
            return v or ""

        # name field: Pipedrive returns "first_name"/"last_name" + "name"
        full_name = p.get("name") or " ".join(filter(None, [p.get("first_name"), p.get("last_name")]))

        # Company lives on the related Organization. /persons/{id} returns
        # `org_id` as a dict ({"name": "..."}); /persons (list) returns it as
        # an int. Both endpoints also include `org_name` separately. We handle
        # all three shapes.
        org_id = p.get("org_id")
        if isinstance(org_id, dict):
            org = org_id.get("name", "") or ""
        else:
            org = p.get("org_name") or ""

        occupation = p.get("job_title") or ""

        # Age from the Date of Birth custom field (Pipedrive has no built-in DOB).
        age = 0
        dob_raw = cf("date_of_birth")
        if dob_raw:
            try:
                dob_d = datetime.strptime(str(dob_raw)[:10], "%Y-%m-%d").date()
                age = (date.today() - dob_d).days // 365
            except ValueError:
                pass

        # City — prefer the custom field, fall back to the built-in postal field
        city = cf("city") or p.get("postal_address_locality", "") or ""

        # Risk score is an enum — resolve option id → label
        risk_key = keys.get("risk_score", "")
        risk = self._resolve_enum(self._person_enum_options, risk_key, p.get(risk_key)) or "low"

        return ClientProfile(
            client_id=str(p.get("id", "")),
            name=full_name,
            age=age,
            occupation=occupation,
            company=org,
            city=city,
            risk_score=risk,
        )

    async def _person_to_risk(self, p: dict) -> RiskAssessment:
        keys = await self._load_person_keys()
        risk_key = keys.get("risk_score", "")
        score = self._resolve_enum(self._person_enum_options, risk_key, p.get(risk_key)) or "low"
        factors_raw = p.get(keys.get("risk_factors", "")) or ""
        factors = [f.strip() for f in str(factors_raw).split("\n") if f.strip()]
        return RiskAssessment(score=score, factors=factors)

    async def _person_to_cross_sell(self, p: dict) -> list[CrossSellOpportunity]:
        keys = await self._load_person_keys()
        items = []
        for n in (1, 2):
            prod_key = keys.get(f"cross_sell_product_{n}")
            pitch_key = keys.get(f"cross_sell_pitch_{n}")
            value_key = keys.get(f"cross_sell_value_{n}")
            product = (p.get(prod_key) or "") if prod_key else ""
            if not product:
                continue
            try:
                est_value = float(p.get(value_key) or 0)
            except (ValueError, TypeError):
                est_value = 0.0
            items.append(CrossSellOpportunity(
                product=str(product),
                eligibility_reason="Based on Pipedrive profile",
                pitch_angle=str(p.get(pitch_key) or "") if pitch_key else "",
                estimated_value=est_value,
            ))
        return items

    async def _deal_to_loan(self, d: dict) -> LoanProduct:
        keys = await self._load_deal_keys()
        principal = float(d.get("value") or 0)
        emi = float(d.get(keys.get("emi_amount", "")) or 0)
        months_paid = int(float(d.get(keys.get("months_paid", "")) or 0))
        tenure = int(float(d.get(keys.get("tenure_months", "")) or 0))
        next_due_raw = d.get(keys.get("next_due_date", "")) or ""
        history_raw = d.get(keys.get("payment_history", "")) or ""
        # Product type is an enum — resolve option id → label
        pt_key = keys.get("product_type", "")
        product_type = self._resolve_enum(self._deal_enum_options, pt_key, d.get(pt_key)) or "personal_loan"
        return LoanProduct(
            product_type=product_type,
            principal=principal,
            emi=emi,
            tenure_months=tenure,
            months_paid=months_paid,
            next_due_date=str(next_due_raw)[:10],
            payment_history=[h.strip() for h in str(history_raw).split(",") if h.strip()],
        )

    # ─── 8-method CRMAdapter contract ─────────────────────────────────────

    async def list_all(self) -> list[ClientProfile]:
        data = await self._get("/persons", params={"limit": 200, "sort": "id"})
        persons = (data.get("data") or []) if isinstance(data, dict) else []
        out = []
        for p in persons:
            if not p:
                continue
            out.append(await self._person_to_profile(p))
        return out

    async def search_client(self, name: str) -> list[ClientProfile]:
        data = await self._get("/persons/search", params={"term": name, "fields": "name", "limit": 20})
        items = ((data.get("data") or {}).get("items") or []) if isinstance(data, dict) else []
        # /persons/search returns wrappers — pull the item then re-fetch full to get custom fields
        out = []
        for wrap in items:
            item = wrap.get("item") if isinstance(wrap, dict) else None
            pid = item.get("id") if item else None
            if not pid:
                continue
            try:
                full = await self._get(f"/persons/{pid}")
                p = (full.get("data") or {}) if isinstance(full, dict) else {}
                out.append(await self._person_to_profile(p))
            except Exception as e:
                logger.warning("Pipedrive person fetch failed: %s", e)
        # Local fuzzy filter to keep the same UX as other adapters
        scored = [(fuzz.partial_ratio(name.lower(), c.name.lower()), c) for c in out]
        scored.sort(reverse=True, key=lambda x: x[0])
        return [c for s, c in scored if s >= 60]

    async def get_client(self, client_id: str) -> Optional[ClientFullProfile]:
        try:
            full = await self._get(f"/persons/{client_id}")
        except Exception:
            return None
        p = (full.get("data") or {}) if isinstance(full, dict) else {}
        if not p:
            return None
        # Run the three downstream Pipedrive fetches concurrently —
        # /persons/{id}/deals and /persons/{id}/activities are independent.
        import asyncio as _asyncio
        profile_task = self._person_to_profile(p)
        risk_task = self._person_to_risk(p)
        cross_sell_task = self._person_to_cross_sell(p)
        portfolio_task = self.get_portfolio(client_id)
        interactions_task = self.get_interactions(client_id)
        profile, risk, cross_sell, products, (interactions, complaints, days_ago) = await _asyncio.gather(
            profile_task, risk_task, cross_sell_task, portfolio_task, interactions_task,
        )
        return ClientFullProfile(
            profile=profile, products=products, risk=risk,
            interactions=interactions, complaints=complaints,
            cross_sell=cross_sell, last_rm_interaction_days_ago=days_ago,
        )

    async def get_portfolio(self, client_id: str) -> list[LoanProduct]:
        try:
            data = await self._get(f"/persons/{client_id}/deals", params={"status": "all_not_deleted", "limit": 20})
            deals = (data.get("data") or []) if isinstance(data, dict) else []
            return [await self._deal_to_loan(d) for d in deals if d]
        except Exception as e:
            logger.warning("Pipedrive portfolio fetch failed: %s", e)
            return []

    async def get_risk(self, client_id: str) -> Optional[RiskAssessment]:
        try:
            full = await self._get(f"/persons/{client_id}")
            p = (full.get("data") or {}) if isinstance(full, dict) else {}
            return await self._person_to_risk(p)
        except Exception:
            return None

    async def get_cross_sell(self, client_id: str) -> list[CrossSellOpportunity]:
        try:
            full = await self._get(f"/persons/{client_id}")
            p = (full.get("data") or {}) if isinstance(full, dict) else {}
            return await self._person_to_cross_sell(p)
        except Exception:
            return []

    async def get_interactions(self, client_id: str) -> tuple[list[Interaction], list[Complaint], int]:
        # Fetch ALL activities (done + not-done). Open complaints are
        # represented as not-done tasks; filtering by done=1 would hide them.
        try:
            data = await self._get(f"/persons/{client_id}/activities", params={"limit": 50})
            activities = (data.get("data") or []) if isinstance(data, dict) else []
        except Exception as e:
            logger.warning("Pipedrive activities fetch failed: %s", e)
            activities = []

        interactions, complaints = [], []
        for a in activities:
            if not a:
                continue
            kind = (a.get("type") or "").lower()  # call | meeting | task | email
            channel_map = {"call": "phone", "meeting": "branch", "email": "email", "task": "phone"}
            channel = channel_map.get(kind, "phone")
            when = (a.get("due_date") or a.get("add_time") or "")[:10]
            summary = a.get("subject") or a.get("note") or ""
            rm = (a.get("owner_name") or "Unknown RM")

            # We use the convention: an activity with subject starting "Complaint:" is a complaint
            if kind == "task" and summary.lower().startswith("complaint"):
                # Try to derive status from subject suffix "[open]" / "[escalated]" / "[resolved]"
                status = "open"
                lower = summary.lower()
                if "[escalated]" in lower:
                    status = "escalated"
                elif "[resolved]" in lower or "[closed]" in lower:
                    status = "resolved"
                complaints.append(Complaint(
                    id=str(a.get("id", "")), date=when,
                    category="General",
                    summary=summary.split(":", 1)[1].strip() if ":" in summary else summary,
                    status=status,
                ))
            else:
                interactions.append(Interaction(
                    date=when, channel=channel, summary=summary[:200], rm_name=rm,
                ))

        # Days since last interaction
        days = 0
        if interactions:
            try:
                last = max(
                    datetime.strptime(i.date, "%Y-%m-%d").date()
                    for i in interactions if len(i.date) >= 10
                )
                days = (date.today() - last).days
            except ValueError:
                days = 0
        return interactions, complaints, days

    async def log_briefing(self, briefing: BriefingLog) -> None:
        """Write a Note to the Person record + update last_rm_interaction_date."""
        keys = await self._load_person_keys()
        today = date.today().isoformat()

        # 1. Note on the Person
        body = (
            f"[SYNC Briefing] RM: {briefing.rm_name}\n"
            f"Duration: {briefing.duration_seconds:.0f}s\n"
            f"Flags: {', '.join(briefing.key_flags) or 'none'}\n"
            f"Suggested pitch: {briefing.suggested_pitch[:240]}"
        )
        try:
            await self._post("/notes", {"person_id": int(briefing.client_id), "content": body})
        except Exception as e:
            logger.warning("Pipedrive note write failed: %s", e)

        # 2. Update last_rm_interaction_date custom field
        last_key = keys.get("last_rm_interaction_date")
        if last_key:
            try:
                await self._put(f"/persons/{briefing.client_id}", {last_key: today})
            except Exception as e:
                logger.warning("Pipedrive last-interaction writeback failed: %s", e)

    # ─── Voice-command action methods (Phase 6) ──────────────────────────

    async def create_note(self, client_id: str, body: str) -> str:
        try:
            r = await self._post("/notes", {"person_id": int(client_id), "content": body})
            return str((r.get("data") or {}).get("id", "")) if isinstance(r, dict) else ""
        except Exception as e:
            logger.warning("Pipedrive create_note failed: %s", e)
            return ""

    async def create_task(self, client_id: str, subject: str, due_date: str, assignee_id: str = "") -> str:
        payload = {
            "subject": subject,
            "type": "task",
            "person_id": int(client_id),
            "due_date": due_date,
            "done": 0,
        }
        if assignee_id:
            try:
                payload["user_id"] = int(assignee_id)
            except ValueError:
                pass
        try:
            r = await self._post("/activities", payload)
            return str((r.get("data") or {}).get("id", "")) if isinstance(r, dict) else ""
        except Exception as e:
            logger.warning("Pipedrive create_task failed: %s", e)
            return ""

    async def update_contact_field(self, client_id: str, field: str, value: str) -> None:
        keys = await self._load_person_keys()
        # Accept either a SYNC canonical name OR a raw Pipedrive key.
        api_key = keys.get(field, field)
        try:
            await self._put(f"/persons/{client_id}", {api_key: value})
        except Exception as e:
            logger.warning("Pipedrive update_contact_field failed: %s", e)

    async def update_complaint_status(self, complaint_id: str, status: str) -> None:
        """Pipedrive doesn't have a Ticket entity — we model complaints as
        activities with subject convention. Re-label the subject + mark done."""
        try:
            # Fetch current activity
            data = await self._get(f"/activities/{complaint_id}")
            a = (data.get("data") or {}) if isinstance(data, dict) else {}
            current_subject = a.get("subject") or "Complaint"
            # Strip any existing [status] tag, add the new one
            import re
            subj = re.sub(r"\s*\[(open|escalated|resolved|closed)\]", "", current_subject, flags=re.IGNORECASE).strip()
            new_subject = f"{subj} [{status}]"
            done = 1 if status in ("resolved", "closed") else 0
            await self._put(f"/activities/{complaint_id}", {"subject": new_subject, "done": done})
        except Exception as e:
            logger.warning("Pipedrive complaint status update failed: %s", e)

    @staticmethod
    def _parse_when(when: str) -> tuple[str, Optional[str]]:
        """Turn a spoken 'when' ('Thursday 4:00 PM', '2026-06-18 16:00') into
        Pipedrive's (due_date, due_time). Weekday names resolve to the NEXT
        occurrence; bare hours in business range default to PM."""
        import re as _re
        from datetime import date as _date, timedelta as _td

        low = (when or "").strip().lower()

        # Explicit ISO date first.
        m = _re.match(r"(\d{4}-\d{2}-\d{2})", low)
        if m:
            due_date = m.group(1)
            rest = low[m.end():]
        else:
            days = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]
            day_idx = next((i for i, d in enumerate(days) if d in low), None)
            if day_idx is not None:
                today = _date.today()
                ahead = (day_idx - today.weekday()) % 7 or 7  # always the NEXT one
                due_date = (today + _td(days=ahead)).isoformat()
            elif "tomorrow" in low:
                due_date = (_date.today() + _td(days=1)).isoformat()
            else:
                due_date = _date.today().isoformat()
            rest = low

        tm = _re.search(r"\b(\d{1,2})(?::(\d{2}))?\s*(am|pm)?\b", rest)
        due_time = None
        if tm:
            hour = int(tm.group(1))
            minutes = tm.group(2) or "00"
            meridiem = tm.group(3)
            if 0 <= hour <= 23:
                if meridiem == "pm" and hour < 12:
                    hour += 12
                elif meridiem == "am" and hour == 12:
                    hour = 0
                elif not meridiem and 1 <= hour <= 7:
                    hour += 12  # business-hours default: bare 1–7 reads as PM
                due_time = f"{hour:02d}:{minutes}"

        # Pipedrive's API treats due_time as UTC and renders it in the
        # account's display timezone — so a spoken local time must be
        # converted, or "4 PM" lands as 9:30 PM on an IST account.
        if due_time:
            try:
                from datetime import datetime as _dt, timezone as _tz
                from zoneinfo import ZoneInfo
                from config import settings as _settings
                local = ZoneInfo(_settings.local_timezone or "Asia/Kolkata")
                y, mo, dd = (int(x) for x in due_date.split("-"))
                hh, mm = (int(x) for x in due_time.split(":"))
                utc_dt = _dt(y, mo, dd, hh, mm, tzinfo=local).astimezone(_tz.utc)
                due_date = utc_dt.date().isoformat()
                due_time = utc_dt.strftime("%H:%M")
            except Exception:
                pass  # worst case: time shows shifted, but the meeting exists
        return due_date, due_time

    async def schedule_follow_up(self, client_id: str, when: str, kind: str, notes: str) -> str:
        type_map = {"call": "call", "meeting": "meeting", "email": "email", "branch_visit": "meeting"}
        pd_type = type_map.get(kind, "call")
        due_date, due_time = self._parse_when(when)
        payload = {
            "subject": f"{pd_type.capitalize()} with client — {when}".strip(),
            "type": pd_type,
            "person_id": int(client_id),
            "due_date": due_date,
            "note": notes,
            "done": 0,
            "busy_flag": True,
        }
        # A timed slot makes it a real calendar meeting in Pipedrive's
        # scheduler view, not just a dated to-do.
        if due_time:
            payload["due_time"] = due_time
            payload["duration"] = "00:30"
        try:
            r = await self._post("/activities", payload)
            return str((r.get("data") or {}).get("id", "")) if isinstance(r, dict) else ""
        except Exception as e:
            logger.warning("Pipedrive schedule_follow_up failed: %s", e)
            return ""
