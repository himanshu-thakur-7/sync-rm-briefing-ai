"""
In-memory mock database with 5 richly detailed sample client profiles.
"""
from datetime import date, timedelta
from models import (
    ClientFullProfile, ClientProfile, LoanProduct, RiskAssessment,
    Interaction, Complaint, CrossSellOpportunity, BriefingLog
)

today = date.today()

def _due(days_ahead: int) -> str:
    return (today + timedelta(days=days_ahead)).isoformat()

def _past(days_ago: int) -> str:
    return (today - timedelta(days=days_ago)).isoformat()


CLIENTS: dict[str, ClientFullProfile] = {
    "client_001": ClientFullProfile(
        profile=ClientProfile(
            client_id="client_001",
            name="Rahul Mehta",
            age=38,
            occupation="Senior Manager",
            company="Infosys",
            city="Bengaluru",
            risk_score="low",
        ),
        products=[
            LoanProduct(
                product_type="home_loan",
                principal=4200000,
                emi=34800,
                tenure_months=240,
                months_paid=14,
                next_due_date=_due(4),
                payment_history=["on_time"] * 14,
            )
        ],
        risk=RiskAssessment(
            score="low",
            factors=["Clean 14-month payment track record", "Stable employment at Infosys"],
        ),
        interactions=[
            Interaction(
                date=_past(45),
                channel="phone",
                summary="Routine check-in, discussed home insurance options. Rahul mentioned he's planning a home renovation in 6 months.",
                rm_name="Deepak Sharma",
            ),
            Interaction(
                date=_past(90),
                channel="branch",
                summary="First loan disbursement meeting. Smooth onboarding.",
                rm_name="Deepak Sharma",
            ),
        ],
        complaints=[
            Complaint(
                id="CMP_001",
                date=_past(7),
                category="Branch Experience",
                summary="Waited 40 minutes at Koramangala branch for document submission. Not acceptable for premium customer.",
                status="open",
            )
        ],
        cross_sell=[
            CrossSellOpportunity(
                product="Personal Loan Top-Up ₹5,00,000",
                eligibility_reason="Salary growth confirmed, 14 months clean repayment history",
                pitch_angle="Position it as a reward for his clean track record — 'You've been our most reliable home loan customer, so we're able to offer you a top-up at a preferential rate.'",
                estimated_value=500000,
            ),
            CrossSellOpportunity(
                product="SIP / Mutual Funds ₹10,000/month",
                eligibility_reason="High disposable income, no existing investment products",
                pitch_angle="Last June he mentioned saving for his daughter's school admission in 2028. A ₹10,000/month SIP gets him there in 3 years. Tie it to his daughter, not to returns.",
                estimated_value=120000,
            ),
        ],
        last_rm_interaction_days_ago=45,
    ),

    "client_002": ClientFullProfile(
        profile=ClientProfile(
            client_id="client_002",
            name="Priya Sharma",
            age=34,
            occupation="Marketing Director",
            company="Unilever",
            city="Mumbai",
            risk_score="very_low",
        ),
        products=[
            LoanProduct(
                product_type="car_loan",
                principal=1200000,
                emi=22500,
                tenure_months=60,
                months_paid=28,
                next_due_date=_due(12),
                payment_history=["on_time"] * 28,
            ),
            LoanProduct(
                product_type="fd",
                principal=800000,
                emi=0,
                tenure_months=24,
                months_paid=6,
                next_due_date=_due(540),
                payment_history=["on_time"] * 6,
            ),
        ],
        risk=RiskAssessment(
            score="very_low",
            factors=["28 consecutive on-time payments", "FD holding demonstrates savings discipline", "Dual income household"],
        ),
        interactions=[
            Interaction(
                date=_past(12),
                channel="email",
                summary="Priya asked about home loan eligibility. Mentioned they're looking to buy a 2BHK in Powai by end of year.",
                rm_name="Anita Verma",
            ),
            Interaction(
                date=_past(60),
                channel="app",
                summary="Self-service FD renewal. No issues.",
                rm_name="Anita Verma",
            ),
        ],
        complaints=[],
        cross_sell=[
            CrossSellOpportunity(
                product="Home Loan ₹65,00,000",
                eligibility_reason="Excellent CIBIL, dual income, existing FD as collateral buffer",
                pitch_angle="She's been house-hunting for 6 months. Her FD matures in 18 months — perfect for down payment. Time this conversation to her timeline, not the product calendar.",
                estimated_value=6500000,
            ),
            CrossSellOpportunity(
                product="Platinum Credit Card",
                eligibility_reason="High income bracket, no credit card with us",
                pitch_angle="She travels frequently for work to Dubai and Singapore. Lead with the lounge access and forex markup waiver, not the cashback.",
                estimated_value=0,
            ),
        ],
        last_rm_interaction_days_ago=12,
    ),

    "client_003": ClientFullProfile(
        profile=ClientProfile(
            client_id="client_003",
            name="Amit Kulkarni",
            age=45,
            occupation="Proprietor",
            company="Kulkarni Textiles",
            city="Pune",
            risk_score="watch",
        ),
        products=[
            LoanProduct(
                product_type="business_loan",
                principal=8500000,
                emi=125000,
                tenure_months=84,
                months_paid=22,
                next_due_date=_due(2),
                payment_history=["on_time"] * 19 + ["missed", "on_time", "delayed_3_days"],
            ),
            LoanProduct(
                product_type="credit_card",
                principal=0,
                emi=0,
                tenure_months=0,
                months_paid=0,
                next_due_date=_due(8),
                payment_history=["on_time", "on_time", "missed", "on_time", "on_time"],
            ),
        ],
        risk=RiskAssessment(
            score="watch",
            factors=[
                "Revenue dip 18% QoQ due to textile sector slowdown",
                "Missed one EMI in last 3 months",
                "CC utilization at 78%",
                "GST filings delayed by 2 quarters",
            ],
        ),
        interactions=[
            Interaction(
                date=_past(30),
                channel="phone",
                summary="Amit mentioned supply chain disruption from Bangladesh. Expects recovery by Q3. Sounded stressed.",
                rm_name="Vijay Nair",
            ),
            Interaction(
                date=_past(85),
                channel="branch",
                summary="Loan restructuring discussion — not yet actioned. Amit wants to extend tenure by 12 months.",
                rm_name="Vijay Nair",
            ),
        ],
        complaints=[
            Complaint(
                id="CMP_002",
                date=_past(20),
                category="Loan Restructuring",
                summary="Submitted restructuring request 20 days ago. No response from credit team yet. Amit is frustrated.",
                status="escalated",
            )
        ],
        cross_sell=[
            CrossSellOpportunity(
                product="Working Capital OD ₹15,00,000",
                eligibility_reason="Business loan track record, textile sector cyclicality",
                pitch_angle="Don't pitch it as 'you need help' — pitch it as 'smart businesses keep a buffer for exactly these cycles.' He's been in textiles 20 years. He knows the cycles. Position it as a tool he deserves, not a lifeline.",
                estimated_value=1500000,
            ),
            CrossSellOpportunity(
                product="Family Floater Health Insurance ₹50L cover",
                eligibility_reason="Son recently joined the business; family of 4; no health cover with the bank",
                pitch_angle="His son just joined the business — frame this as protecting the family's two breadwinners. The premium is tax-deductible under Section 80D. Not a lifestyle product — a backstop.",
                estimated_value=24000,
            ),
        ],
        last_rm_interaction_days_ago=30,
    ),

    "client_004": ClientFullProfile(
        profile=ClientProfile(
            client_id="client_004",
            name="Sneha Reddy",
            age=29,
            occupation="Software Engineer",
            company="Google",
            city="Hyderabad",
            risk_score="very_low",
        ),
        products=[
            LoanProduct(
                product_type="personal_loan",
                principal=600000,
                emi=14200,
                tenure_months=48,
                months_paid=8,
                next_due_date=_due(18),
                payment_history=["on_time"] * 8,
            ),
        ],
        risk=RiskAssessment(
            score="very_low",
            factors=["Google ESOP vesting cycle confirmed", "High salary-to-EMI ratio (8:1)", "Young professional with growth trajectory"],
        ),
        interactions=[
            Interaction(
                date=_past(5),
                channel="app",
                summary="Sneha checked home loan eligibility on the app. Spent 8 minutes on the calculator.",
                rm_name="Rekha Pillai",
            ),
            Interaction(
                date=_past(65),
                channel="phone",
                summary="Personal loan disbursement follow-up. Smooth process. She asked about investment options.",
                rm_name="Rekha Pillai",
            ),
        ],
        complaints=[],
        cross_sell=[
            CrossSellOpportunity(
                product="Home Loan ₹75,00,000",
                eligibility_reason="Google ESOP + salary, excellent CIBIL 812, actively searching on app",
                pitch_angle="She's already done the math — she just needs someone to make it feel real. Don't sell the loan, help her visualize the flat. 'Your EMI would be ₹58,000, which is less than what most people pay in Hyderabad rent.' Lead with that.",
                estimated_value=7500000,
            ),
            CrossSellOpportunity(
                product="ESOP-Backed Overdraft ₹20,00,000",
                eligibility_reason="Significant ESOP vesting in 8 months",
                pitch_angle="Her ESOPs vest in 8 months. She probably doesn't know she can use them as collateral today. Frame it as unlocking value she's already earned.",
                estimated_value=2000000,
            ),
        ],
        last_rm_interaction_days_ago=5,
    ),

    "client_005": ClientFullProfile(
        profile=ClientProfile(
            client_id="client_005",
            name="Vikram Desai",
            age=52,
            occupation="Managing Director",
            company="Desai Infrastructure Ltd",
            city="Ahmedabad",
            risk_score="high",
        ),
        products=[
            LoanProduct(
                product_type="business_loan",
                principal=25000000,
                emi=380000,
                tenure_months=96,
                months_paid=18,
                next_due_date=_due(3),
                payment_history=["on_time"] * 14 + ["missed", "missed", "delayed_7_days", "on_time"],
            ),
            LoanProduct(
                product_type="credit_card",
                principal=0,
                emi=0,
                tenure_months=0,
                months_paid=0,
                next_due_date=_due(5),
                payment_history=["on_time", "missed", "missed", "on_time", "missed"],
            ),
        ],
        risk=RiskAssessment(
            score="high",
            factors=[
                "CC utilization at 92% — maxed out",
                "2 missed business loan EMIs in last 4 months",
                "Infrastructure sector slowdown, 3 projects stalled",
                "Personal guarantor on 2 other loans with different banks",
                "NPA classification risk in 45 days if pattern continues",
            ],
        ),
        interactions=[
            Interaction(
                date=_past(22),
                channel="phone",
                summary="Vikram called to discuss payment difficulty. 2 govt contracts delayed by 6 months. Mentioned expecting payment by month end.",
                rm_name="Suresh Iyer",
            ),
            Interaction(
                date=_past(75),
                channel="branch",
                summary="Quarterly review meeting. Discussed new project pipeline worth ₹80Cr. Seemed optimistic.",
                rm_name="Suresh Iyer",
            ),
        ],
        complaints=[
            Complaint(
                id="CMP_003",
                date=_past(15),
                category="Late Payment Charges",
                summary="Vikram disputes ₹42,000 late payment charges. Claims he was given verbal assurance of grace period extension.",
                status="open",
            )
        ],
        cross_sell=[
            CrossSellOpportunity(
                product="CC Balance-to-PL Transfer ₹8,00,000",
                eligibility_reason="CC at 92%, PL would cut interest cost by 40%",
                pitch_angle="Don't pitch this as 'we noticed your CC is maxed.' Pitch it as 'I've found a way to save you about ₹3 lakh in interest this year.' Let him do the math. The answer is yes.",
                estimated_value=800000,
            ),
            CrossSellOpportunity(
                product="Personal account separation + term insurance ₹2Cr",
                eligibility_reason="Personal guarantor on multiple business loans; family exposure",
                pitch_angle="His personal financial life is fused with the company's. Term cover ringfences his family from the infra exposure. Speak about his daughter (she just started Class 11) — protection, not investment.",
                estimated_value=180000,
            ),
        ],
        last_rm_interaction_days_ago=22,
    ),
}


# In-memory briefing log store
BRIEFING_LOGS: list[BriefingLog] = []

# Pre-seeded historical briefing logs for a realistic demo
import uuid
from datetime import datetime, timedelta as td

_now = datetime.now()

def _ts(minutes_ago: int) -> str:
    return (_now - td(minutes=minutes_ago)).isoformat()

BRIEFING_LOGS = [
    BriefingLog(
        briefing_id=str(uuid.uuid4()),
        client_id="client_005",
        client_name="Vikram Desai",
        rm_id="rm_003",
        rm_name="Suresh Iyer",
        timestamp=_ts(12),
        duration_seconds=52,
        key_flags=["risk_high", "cc_utilization_92%", "2_missed_emis", "complaint_open"],
        suggested_pitch="CC debt restructure to Personal Loan — saves ₹3L in interest",
        call_id="ringg_demo_001",
        risk_score="high",
        latency_ms=340,
    ),
    BriefingLog(
        briefing_id=str(uuid.uuid4()),
        client_id="client_001",
        client_name="Rahul Mehta",
        rm_id="rm_001",
        rm_name="Deepak Sharma",
        timestamp=_ts(28),
        duration_seconds=38,
        key_flags=["complaint_open", "emi_due_4_days"],
        suggested_pitch="SIP for daughter's education — ₹10K/month, 2028 goal",
        call_id="ringg_demo_002",
        risk_score="low",
        latency_ms=285,
    ),
    BriefingLog(
        briefing_id=str(uuid.uuid4()),
        client_id="client_004",
        client_name="Sneha Reddy",
        rm_id="rm_004",
        rm_name="Rekha Pillai",
        timestamp=_ts(55),
        duration_seconds=41,
        key_flags=["home_loan_intent_detected", "esop_vesting_8_months"],
        suggested_pitch="Home loan ₹75L — she's done the math, just needs the nudge",
        call_id="ringg_demo_003",
        risk_score="very_low",
        latency_ms=312,
    ),
    BriefingLog(
        briefing_id=str(uuid.uuid4()),
        client_id="client_003",
        client_name="Amit Kulkarni",
        rm_id="rm_002",
        rm_name="Vijay Nair",
        timestamp=_ts(90),
        duration_seconds=47,
        key_flags=["risk_watch", "restructuring_pending_20_days", "complaint_escalated", "emi_due_2_days"],
        suggested_pitch="Working capital OD ₹15L — frame as a strategic buffer, not a lifeline",
        call_id="ringg_demo_004",
        risk_score="watch",
        latency_ms=401,
    ),
]
