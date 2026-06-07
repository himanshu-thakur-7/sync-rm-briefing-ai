"""SQLModel persistent tables for SYNC."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

from sqlalchemy import JSON, Column, LargeBinary
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(timezone.utc)


class CRMConnection(SQLModel, table=True):
    """One row per (bank, CRM provider, label) triple."""

    __tablename__ = "crm_connections"

    id: str = Field(primary_key=True)
    provider: str = Field(index=True)  # hubspot | salesforce | zoho | dynamics | freshworks | leadsquared | fake_leadsquared | mock
    label: str = ""  # Human label, e.g. "HubSpot (Prod)"
    status: str = Field(default="active")  # active | disconnected | error
    auth_method: str = Field(default="oauth2")  # oauth2 | api_key | none
    metadata_json: dict = Field(default_factory=dict, sa_column=Column(JSON))  # provider-specific (portal_id, instance_url, etc.)
    last_sync_at: Optional[datetime] = None
    last_error: Optional[str] = None
    is_default: bool = Field(default=False)
    created_at: datetime = Field(default_factory=_now)
    updated_at: datetime = Field(default_factory=_now)


class OAuthToken(SQLModel, table=True):
    """Encrypted token payload for a CRMConnection."""

    __tablename__ = "oauth_tokens"

    id: Optional[int] = Field(default=None, primary_key=True)
    connection_id: str = Field(index=True, unique=True)
    encrypted_blob: bytes = Field(sa_column=Column(LargeBinary))
    expires_at: Optional[datetime] = None
    refreshed_at: datetime = Field(default_factory=_now)


class OAuthState(SQLModel, table=True):
    """Short-lived CSRF state for OAuth authorize→callback handoff."""

    __tablename__ = "oauth_states"

    state: str = Field(primary_key=True)
    provider: str
    label: str = ""
    created_at: datetime = Field(default_factory=_now)


class FieldMapping(SQLModel, table=True):
    """Per-connection canonical→bank-field override."""

    __tablename__ = "field_mappings"

    id: Optional[int] = Field(default=None, primary_key=True)
    connection_id: str = Field(index=True)
    object_type: str  # contact | deal | task | ticket | etc.
    canonical_name: str  # SYNC's name, e.g. "risk_score"
    bank_field_name: str  # The bank's actual CRM field name, e.g. "custom_risk_v2"


class ProvisioningStatus(SQLModel, table=True):
    """Snapshot of which custom fields are present/missing per connection."""

    __tablename__ = "provisioning_status"

    id: Optional[int] = Field(default=None, primary_key=True)
    connection_id: str = Field(index=True)
    object_type: str
    field_name: str
    status: str  # present | missing | type_mismatch
    detail: Optional[str] = None
    checked_at: datetime = Field(default_factory=_now)


class BriefingLogRow(SQLModel, table=True):
    """Persistent mirror of an in-memory BriefingLog."""

    __tablename__ = "briefing_logs"

    briefing_id: str = Field(primary_key=True)
    connection_id: str = Field(index=True)
    client_id: str = Field(index=True)
    client_name: str
    rm_id: str
    rm_name: str
    timestamp: datetime
    duration_seconds: float
    key_flags: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    suggested_pitch: str = ""
    call_id: str = Field(index=True)
    risk_score: str = ""
    latency_ms: Optional[int] = None
    recording_url: Optional[str] = None
    transcript: Optional[str] = None


class WebhookEvent(SQLModel, table=True):
    """Lifecycle row for every webhook ingest (Ringg, OAuth providers, etc.)."""

    __tablename__ = "webhook_events"

    id: Optional[int] = Field(default=None, primary_key=True)
    source: str = Field(index=True)  # ringg | hubspot | salesforce | ...
    event_type: str = Field(index=True)
    call_id: Optional[str] = Field(default=None, index=True)
    status: str = Field(default="received")  # received | processing | processed | error
    payload: dict = Field(default_factory=dict, sa_column=Column(JSON))
    error: Optional[str] = None
    received_at: datetime = Field(default_factory=_now)
    processed_at: Optional[datetime] = None


class CommandLog(SQLModel, table=True):
    """Phase 6: voice-command audit log."""

    __tablename__ = "command_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    connection_id: str = Field(index=True)
    rm_id: str = ""
    client_id: Optional[str] = Field(default=None, index=True)
    raw_transcript: str
    parsed_tool: Optional[str] = None
    parsed_args: dict = Field(default_factory=dict, sa_column=Column(JSON))
    status: str = Field(default="pending")  # pending | confirmed | executed | failed | cancelled
    error: Optional[str] = None
    action_id_in_crm: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    executed_at: Optional[datetime] = None


class SaveCallPlay(SQLModel, table=True):
    """Round 2: an autonomous outbound 'save call' the Risk Radar wants to place."""

    __tablename__ = "save_call_plays"

    id: Optional[int] = Field(default=None, primary_key=True)
    connection_id: str = Field(index=True)
    client_id: str = Field(index=True)
    client_name: str = ""
    client_phone: str = ""
    trigger_type: str = ""  # npa_risk | aging_complaint | emi_overdue_soon | winback | proactive_crosssell
    urgency: str = "MEDIUM"  # CRITICAL | HIGH | MEDIUM | LOW
    objective: str = ""
    talking_points: list = Field(default_factory=list, sa_column=Column(JSON))
    rationale: str = ""
    matched_triggers: list = Field(default_factory=list, sa_column=Column(JSON))
    status: str = Field(default="queued")  # queued | calling | transferred | completed | failed | dismissed
    call_id: Optional[str] = Field(default=None, index=True)
    outcome: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
    called_at: Optional[datetime] = None


class MorningBriefSchedule(SQLModel, table=True):
    """Round 3: a recurring daily-standup call SYNC places to the RM/Advisor."""

    __tablename__ = "morning_brief_schedules"

    id: Optional[int] = Field(default=None, primary_key=True)
    rm_id: str = ""
    rm_name: str = ""
    rm_phone: str = ""
    connection_id: str = Field(index=True)
    hour_local: int = 7
    minute_local: int = 45
    weekday_mask: int = 31  # bit 0=Mon ... bit 6=Sun; 31 = Mon-Fri
    timezone: str = "Asia/Kolkata"  # IANA name
    company_name: str = "Acme"
    language_style: str = "english_only"  # english_only | auto
    enabled: bool = True
    last_called_at: Optional[datetime] = None
    next_call_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=_now)


class MorningBriefCall(SQLModel, table=True):
    """Round 3: history of a single morning-brief call."""

    __tablename__ = "morning_brief_calls"

    id: Optional[int] = Field(default=None, primary_key=True)
    schedule_id: int = Field(index=True)
    call_id: str = Field(index=True, unique=True)
    agenda_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    questions_asked: int = 0
    actions_executed: int = 0
    summary: str = ""
    started_at: datetime = Field(default_factory=_now)
    ended_at: Optional[datetime] = None


class CallAnalysis(SQLModel, table=True):
    """Round 2: GPT-4o post-call intelligence for any completed call."""

    __tablename__ = "call_analyses"

    id: Optional[int] = Field(default=None, primary_key=True)
    call_id: str = Field(index=True, unique=True)
    client_id: Optional[str] = Field(default=None, index=True)
    connection_id: Optional[str] = None
    call_kind: str = "briefing"  # briefing | save_call | manual
    sentiment_label: str = "neutral"
    sentiment_score: int = 50  # 0-100
    sentiment_timeline: list = Field(default_factory=list, sa_column=Column(JSON))
    objections: list = Field(default_factory=list, sa_column=Column(JSON))
    commitments: list = Field(default_factory=list, sa_column=Column(JSON))
    churn_delta: float = 0.0  # -1 (reduced) .. +1 (increased)
    churn_label: str = "unchanged"  # reduced | unchanged | increased
    next_best_action: dict = Field(default_factory=dict, sa_column=Column(JSON))
    summary: str = ""
    nba_executed: bool = False
    nba_action_id: Optional[str] = None
    created_at: datetime = Field(default_factory=_now)
