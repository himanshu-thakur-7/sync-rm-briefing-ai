"""
Generates a knowledge base document from all client data,
formatted for Ringg AI upload (inbound call mode).
"""
from models import ClientFullProfile


def _format_rupees(amount: float) -> str:
    if amount >= 10000000:
        return f"₹{amount/10000000:.1f}Cr"
    elif amount >= 100000:
        return f"₹{amount/100000:.0f}L"
    elif amount >= 1000:
        return f"₹{amount/1000:.0f}K"
    return f"₹{amount:.0f}"


def generate_kb_document(clients: list[ClientFullProfile]) -> str:
    """
    Generates a structured text document containing all client data,
    formatted so the Ringg AI agent can look up any client by name
    during an inbound call.
    """
    sections = []

    for client in clients:
        p = client.profile
        r = client.risk
        lines = [f"=== CLIENT: {p.name} ==="]
        lines.append(f"Full Name: {p.name}")
        lines.append(f"Age: {p.age}")
        lines.append(f"Occupation: {p.occupation} at {p.company}, {p.city}")
        lines.append("")

        lines.append("PORTFOLIO:")
        for prod in client.products:
            missed = sum(1 for h in prod.payment_history if h != "on_time")
            record = f"{prod.months_paid} consecutive on-time payments" if missed == 0 else f"{missed} missed payments in last {prod.months_paid} months"
            lines.append(
                f"- {prod.product_type.replace('_',' ').title()}: "
                f"{_format_rupees(prod.principal)} principal, "
                f"{_format_rupees(prod.emi)} EMI/month"
            )
            lines.append(f"  Tenure: {prod.tenure_months} months, {prod.months_paid} months paid, next due: {prod.next_due_date}")
            lines.append(f"  Payment Record: {record}")
        lines.append("")

        lines.append(f"RISK: {r.score.title()}")
        lines.append(f"Factors: {', '.join(r.factors)}")
        lines.append("")

        lines.append(f"LAST RM CONTACT: {client.last_rm_interaction_days_ago} days ago")
        if client.interactions:
            last = client.interactions[0]
            lines.append(f"Channel: {last.channel.title()}")
            lines.append(f"Summary: {last.summary}")
        lines.append("")

        open_complaints = [c for c in client.complaints if c.status == "open"]
        if open_complaints:
            lines.append("OPEN COMPLAINTS:")
            for c in open_complaints:
                lines.append(f'- {c.category} ({c.date}, {c.status.upper()})')
                lines.append(f'  "{c.summary}"')
        else:
            lines.append("OPEN COMPLAINTS: None")
        lines.append("")

        if client.cross_sell:
            lines.append("CROSS-SELL OPPORTUNITIES:")
            for i, cs in enumerate(client.cross_sell, 1):
                lines.append(f"{i}. {cs.product}")
                lines.append(f"   Why: {cs.eligibility_reason}")
                lines.append(f"   Pitch Angle: {cs.pitch_angle}")
        lines.append("")
        lines.append(f"=== END CLIENT ===")
        lines.append("")
        sections.append("\n".join(lines))

    return "\n".join(sections)


if __name__ == "__main__":
    import sys
    sys.path.insert(0, "..")
    import database
    doc = generate_kb_document(list(database.CLIENTS.values()))
    print(doc)
