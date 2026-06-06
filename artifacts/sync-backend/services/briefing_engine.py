"""
GPT-4o briefing generation engine.
Generates a natural 45-second RM briefing script from structured client data.
Falls back to a template-based briefing if OpenAI is not configured.
"""
import os
import logging
from models import ClientFullProfile

logger = logging.getLogger(__name__)

BRIEFING_SYSTEM_PROMPT = """
You generate RM briefing scripts for SYNC, a voice AI co-pilot for Indian bank Relationship Managers.
Given structured client data, produce a natural, conversational 45-second briefing script.

Rules:
1. Sound like a sharp colleague, NOT a report. Narrate, don't list.
2. Order: Identity → Portfolio → Risk flags → Relationship gap → The play
3. If risk is HIGH or WATCH, or there's an open complaint, mention it clearly
4. Include 1-2 natural Hinglish phrases (e.g., "EMI time pe aa raha hai", "kuch aur chahiye?")
5. End with the cross-sell recommendation tied to the client's LIFE context, not just product eligibility
6. Keep under 120 words (maps to ~45 seconds of speech)
7. Use contractions, filler phrases ("so here's the thing", "honestly", "look")
8. Never say "according to our records" or "as per your CRM"
9. If there's an open complaint, ALWAYS mention it — worst thing is RM walking in unaware
"""


def _format_rupees(amount: float) -> str:
    """Format amount in Indian rupee shorthand."""
    if amount >= 10000000:
        return f"₹{amount/10000000:.1f}Cr"
    elif amount >= 100000:
        return f"₹{amount/100000:.0f}L"
    elif amount >= 1000:
        return f"₹{amount/1000:.0f}K"
    return f"₹{amount:.0f}"


def _template_briefing(client: ClientFullProfile) -> str:
    """Generate a template-based briefing when OpenAI is not configured."""
    p = client.profile
    r = client.risk
    products = client.products
    complaints = client.complaints
    cross_sell = client.cross_sell
    days = client.last_rm_interaction_days_ago

    open_complaints = [c for c in complaints if c.status == "open"]

    lines = []

    # Identity
    lines.append(f"Alright, so {p.name} — {p.age}, {p.occupation} at {p.company} in {p.city}.")

    # Portfolio
    if products:
        prod = products[0]
        lines.append(
            f"{'He' if p.age > 35 else 'She'}'s got a {prod.product_type.replace('_', ' ')}, "
            f"{_format_rupees(prod.principal)}, EMI is {_format_rupees(prod.emi)}/month. "
            f"Next one's due {prod.next_due_date}."
        )
        missed = sum(1 for h in prod.payment_history if h != "on_time")
        if missed == 0:
            lines.append(f"EMI time pe aa raha hai — clean record, {prod.months_paid} months straight.")
        elif missed == 1:
            lines.append(f"One missed payment in the last few months — keep an eye on it.")
        else:
            lines.append(f"Honestly, {missed} missed payments. That's the risk flag here.")

    # Risk
    if r.score in ("high", "watch"):
        lines.append(f"Risk is {r.score.upper()}. Main factors: {', '.join(r.factors[:2])}.")

    # Relationship gap
    lines.append(f"Last contact was {days} days ago.")

    # Complaints
    if open_complaints:
        c = open_complaints[0]
        lines.append(f"One thing — there's an open complaint about {c.category}. {c.summary[:80]}. Don't get caught off guard.")

    # Cross-sell
    if cross_sell:
        cs = cross_sell[0]
        lines.append(f"Here's your play: {cs.pitch_angle[:120]}")

    lines.append("That's the quick sync. Kuch aur chahiye, ya ready ho?")

    return " ".join(lines)


async def generate_briefing(client: ClientFullProfile) -> str:
    """
    Generate a briefing script using GPT-4o.
    Falls back to template if OpenAI API key is not configured.
    """
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        logger.info("OPENAI_API_KEY not set — using template briefing")
        return _template_briefing(client)

    try:
        from openai import AsyncOpenAI

        base_url = os.environ.get("AI_INTEGRATIONS_OPENAI_BASE_URL") or "https://api.openai.com/v1"
        openai_client = AsyncOpenAI(api_key=openai_key, base_url=base_url)

        p = client.profile
        r = client.risk
        products_summary = "\n".join([
            f"  - {prod.product_type.replace('_',' ').title()}: {_format_rupees(prod.principal)} principal, "
            f"{_format_rupees(prod.emi)}/month EMI, {prod.months_paid}/{prod.tenure_months} months paid, "
            f"next due {prod.next_due_date}, "
            f"missed payments: {sum(1 for h in prod.payment_history if h != 'on_time')}"
            for prod in client.products
        ])
        complaints_summary = "\n".join([
            f"  - [{c.status.upper()}] {c.category}: {c.summary}"
            for c in client.complaints
        ]) or "None"
        cross_sell_summary = "\n".join([
            f"  - {cs.product}: {cs.pitch_angle}"
            for cs in client.cross_sell
        ]) or "None"

        user_message = f"""
CLIENT DATA:
Name: {p.name}, Age: {p.age}
Occupation: {p.occupation} at {p.company}, {p.city}
Last RM contact: {client.last_rm_interaction_days_ago} days ago

PORTFOLIO:
{products_summary}

RISK: {r.score.upper()}
Factors: {', '.join(r.factors)}

COMPLAINTS:
{complaints_summary}

CROSS-SELL OPPORTUNITIES:
{cross_sell_summary}

Generate the briefing script now. Keep it under 120 words. Start directly — no preamble.
"""
        response = await openai_client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": BRIEFING_SYSTEM_PROMPT},
                {"role": "user", "content": user_message},
            ],
            max_tokens=300,
            temperature=0.7,
        )
        return response.choices[0].message.content.strip()

    except Exception as e:
        logger.warning(f"OpenAI briefing generation failed: {e}. Using template fallback.")
        return _template_briefing(client)
