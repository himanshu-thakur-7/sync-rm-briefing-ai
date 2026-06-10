from pydantic import BaseModel
from typing import Optional


class ClientProfile(BaseModel):
    client_id: str
    name: str
    age: int
    occupation: str
    company: str
    city: str
    risk_score: str  # very_low | low | medium | watch | high


class LoanProduct(BaseModel):
    product_type: str  # home_loan | personal_loan | business_loan | car_loan | credit_card | fd
    principal: float
    emi: float
    tenure_months: int
    months_paid: int
    next_due_date: str
    payment_history: list[str]  # ["on_time", "on_time", "missed", "on_time"]


class RiskAssessment(BaseModel):
    score: str  # very_low | low | medium | watch | high
    factors: list[str]


class Interaction(BaseModel):
    date: str
    channel: str  # phone | branch | email | app
    summary: str
    rm_name: str


class Complaint(BaseModel):
    id: str
    date: str
    category: str
    summary: str
    status: str  # open | resolved | escalated


class CrossSellOpportunity(BaseModel):
    product: str
    eligibility_reason: str
    pitch_angle: str
    estimated_value: float


class ClientFullProfile(BaseModel):
    profile: ClientProfile
    products: list[LoanProduct]
    risk: RiskAssessment
    interactions: list[Interaction]
    complaints: list[Complaint]
    cross_sell: list[CrossSellOpportunity]
    last_rm_interaction_days_ago: int


class ClientInteractions(BaseModel):
    interactions: list[Interaction]
    complaints: list[Complaint]
    last_rm_interaction_days_ago: int


class BriefingLog(BaseModel):
    briefing_id: str
    client_id: str
    client_name: str
    rm_id: str
    rm_name: str
    timestamp: str
    duration_seconds: float
    key_flags: list[str]
    suggested_pitch: str
    call_id: str
    risk_score: str
    latency_ms: Optional[int] = None
    # Optional bag for extras (e.g. cross_sell_value used by the ROI ledger).
    extra: dict = {}


class BriefingStats(BaseModel):
    syncs_today: int
    avg_time_saved_minutes: float
    cross_sells_surfaced: int
    complaints_flagged: int
    avg_latency_ms: Optional[int] = None


class SyncRequest(BaseModel):
    client_id: str
    rm_phone: str
    rm_name: str


class SyncResponse(BaseModel):
    call_id: str
    status: str
    briefing_preview: str


class RinggWebhookPayload(BaseModel):
    call_id: str
    event_type: str
    duration_seconds: Optional[float] = None
    transcript: Optional[str] = None
    latency_ms: Optional[int] = None


class ErrorResponse(BaseModel):
    error: str
