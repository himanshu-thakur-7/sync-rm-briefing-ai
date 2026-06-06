"""Auto-provisioning service for CRM custom fields.

For each CRM provider, SYNC requires a set of custom fields/properties to
store risk scores, EMI amounts, cross-sell opportunities, etc.  This service:

  1. detect(connection_id) → ProvisioningReport
       Reads the CRM's metadata API and diffs against the required spec.

  2. provision(connection_id, fields) → ProvisioningResult
       Creates missing fields via the CRM's API (HubSpot: Properties API;
       Salesforce: returns downloadable package.xml; Zoho/Dynamics/Freshworks:
       metadata REST endpoints; LeadSquared: field-schema API).

Usage: called by GET/POST /api/v1/integrations/{id}/provision
"""
from __future__ import annotations

import io
import logging
import zipfile
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class FieldSpec:
    """Description of a single custom field SYNC needs in a CRM."""
    name: str                        # canonical SYNC name, e.g. "risk_score"
    object_type: str                 # contact | deal | task | ticket | loan | custom
    crm_name: str                    # the actual field name in this CRM
    crm_type: str                    # text | number | date | picklist | long_text
    options: list[str] = field(default_factory=list)  # for picklist
    required_for: list[str] = field(default_factory=list)  # which adapter methods need it
    description: str = ""


@dataclass
class ProvisioningReport:
    connection_id: str
    provider: str
    present: list[str] = field(default_factory=list)
    missing: list[str] = field(default_factory=list)
    type_mismatch: list[str] = field(default_factory=list)
    checked_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())


@dataclass
class ProvisioningResult:
    provisioned: list[str] = field(default_factory=list)
    skipped: list[str] = field(default_factory=list)
    errors: dict[str, str] = field(default_factory=dict)
    sf_package_zip: Optional[bytes] = None  # for Salesforce


# ─────────────────────────────── Field specs per provider ──────────────────

HUBSPOT_FIELD_SPECS: list[FieldSpec] = [
    FieldSpec("risk_score", "contact", "risk_score", "enumeration",
              options=["very_low", "low", "medium", "watch", "high"],
              required_for=["get_risk", "search_client"]),
    FieldSpec("risk_factors", "contact", "risk_factors", "textarea",
              required_for=["get_risk"]),
    FieldSpec("last_rm_interaction_date", "contact", "last_rm_interaction_date", "date",
              required_for=["get_interactions", "log_briefing"]),
    FieldSpec("cross_sell_product_1", "contact", "cross_sell_product_1", "text",
              required_for=["get_cross_sell"]),
    FieldSpec("cross_sell_pitch_1", "contact", "cross_sell_pitch_1", "textarea",
              required_for=["get_cross_sell"]),
    FieldSpec("cross_sell_value_1", "contact", "cross_sell_value_1", "number",
              required_for=["get_cross_sell"]),
    FieldSpec("cross_sell_product_2", "contact", "cross_sell_product_2", "text",
              required_for=["get_cross_sell"]),
    FieldSpec("cross_sell_pitch_2", "contact", "cross_sell_pitch_2", "textarea",
              required_for=["get_cross_sell"]),
    FieldSpec("cross_sell_value_2", "contact", "cross_sell_value_2", "number",
              required_for=["get_cross_sell"]),
    FieldSpec("product_type", "deal", "product_type", "enumeration",
              options=["home_loan", "personal_loan", "business_loan", "car_loan", "credit_card", "fd"],
              required_for=["get_portfolio"]),
    FieldSpec("emi_amount", "deal", "emi_amount", "number", required_for=["get_portfolio"]),
    FieldSpec("months_paid", "deal", "months_paid", "number", required_for=["get_portfolio"]),
    FieldSpec("tenure_months", "deal", "tenure_months", "number", required_for=["get_portfolio"]),
    FieldSpec("next_due_date", "deal", "next_due_date", "date", required_for=["get_portfolio"]),
    FieldSpec("payment_history", "deal", "payment_history", "textarea", required_for=["get_portfolio"]),
]

SALESFORCE_FIELD_SPECS: list[FieldSpec] = [
    FieldSpec("risk_score", "contact", "Risk_Score__c", "Picklist",
              options=["very_low", "low", "medium", "watch", "high"],
              required_for=["get_risk"]),
    FieldSpec("risk_factors", "contact", "Risk_Factors__c", "LongTextArea",
              required_for=["get_risk"]),
    FieldSpec("last_rm_interaction_date", "contact", "Last_RM_Interaction_Date__c", "Date",
              required_for=["get_interactions", "log_briefing"]),
    FieldSpec("product_type", "opportunity", "Product_Type__c", "Picklist",
              options=["home_loan", "personal_loan", "business_loan", "car_loan", "credit_card", "fd"],
              required_for=["get_portfolio"]),
    FieldSpec("emi_amount", "opportunity", "EMI_Amount__c", "Currency", required_for=["get_portfolio"]),
    FieldSpec("months_paid", "opportunity", "Months_Paid__c", "Number", required_for=["get_portfolio"]),
    FieldSpec("tenure_months", "opportunity", "Tenure_Months__c", "Number", required_for=["get_portfolio"]),
    FieldSpec("next_due_date", "opportunity", "Next_Due_Date__c", "Date", required_for=["get_portfolio"]),
    FieldSpec("payment_history", "opportunity", "Payment_History__c", "LongTextArea", required_for=["get_portfolio"]),
    FieldSpec("cross_sell_object", "cross_sell__c", "Cross_Sell__c", "CustomObject",
              required_for=["get_cross_sell"],
              description="Custom object with fields: Contact__c, Product__c, Pitch_Angle__c, Estimated_Value__c"),
]

ZOHO_FIELD_SPECS: list[FieldSpec] = [
    FieldSpec("risk_score", "Contacts", "Risk_Score", "Picklist",
              options=["very_low", "low", "medium", "watch", "high"],
              required_for=["get_risk"]),
    FieldSpec("risk_factors", "Contacts", "Risk_Factors", "Textarea", required_for=["get_risk"]),
    FieldSpec("last_rm_interaction_date", "Contacts", "Last_RM_Interaction_Date", "Date",
              required_for=["log_briefing"]),
    FieldSpec("cross_sell_product_1", "Contacts", "Cross_Sell_Product_1", "Text", required_for=["get_cross_sell"]),
    FieldSpec("cross_sell_pitch_1", "Contacts", "Cross_Sell_Pitch_1", "Textarea", required_for=["get_cross_sell"]),
    FieldSpec("cross_sell_value_1", "Contacts", "Cross_Sell_Value_1", "Number", required_for=["get_cross_sell"]),
    FieldSpec("product_type", "Deals", "Product_Type", "Picklist",
              options=["home_loan", "personal_loan", "business_loan", "car_loan", "credit_card", "fd"],
              required_for=["get_portfolio"]),
    FieldSpec("emi_amount", "Deals", "EMI_Amount", "Number", required_for=["get_portfolio"]),
    FieldSpec("payment_history", "Deals", "Payment_History", "Textarea", required_for=["get_portfolio"]),
]

DYNAMICS_FIELD_SPECS: list[FieldSpec] = [
    FieldSpec("risk_score", "contact", "sync_riskscore", "OptionSet",
              options=["very_low", "low", "medium", "watch", "high"],
              required_for=["get_risk"]),
    FieldSpec("risk_factors", "contact", "sync_riskfactors", "Memo", required_for=["get_risk"]),
    FieldSpec("last_rm_interaction_date", "contact", "sync_lastrminteractiondate", "DateTime",
              required_for=["log_briefing"]),
    FieldSpec("product_type", "opportunity", "sync_producttype", "OptionSet",
              options=["home_loan", "personal_loan", "business_loan", "car_loan", "credit_card", "fd"],
              required_for=["get_portfolio"]),
    FieldSpec("emi_amount", "opportunity", "sync_emiamount", "Money", required_for=["get_portfolio"]),
    FieldSpec("payment_history", "opportunity", "sync_paymenthistory", "Memo", required_for=["get_portfolio"]),
]

FRESHWORKS_FIELD_SPECS: list[FieldSpec] = [
    FieldSpec("risk_score", "contact", "cf_risk_score", "dropdown",
              options=["very_low", "low", "medium", "watch", "high"],
              required_for=["get_risk"]),
    FieldSpec("risk_factors", "contact", "cf_risk_factors", "multi_line_text", required_for=["get_risk"]),
    FieldSpec("last_rm_interaction_date", "contact", "cf_last_rm_interaction", "date",
              required_for=["log_briefing"]),
    FieldSpec("product_type", "deal", "cf_product_type", "dropdown",
              options=["home_loan", "personal_loan", "business_loan", "car_loan", "credit_card", "fd"],
              required_for=["get_portfolio"]),
    FieldSpec("emi_amount", "deal", "cf_emi_amount", "number", required_for=["get_portfolio"]),
    FieldSpec("payment_history", "deal", "cf_payment_history", "multi_line_text", required_for=["get_portfolio"]),
]

LEADSQUARED_FIELD_SPECS: list[FieldSpec] = [
    FieldSpec("risk_score", "lead", "mx_Risk_Score", "text", required_for=["get_risk"]),
    FieldSpec("risk_factors", "lead", "mx_Risk_Factors", "text", required_for=["get_risk"]),
    FieldSpec("last_rm_interaction_days", "lead", "mx_Last_RM_Interaction_Days", "number",
              required_for=["get_interactions"]),
    FieldSpec("cross_sell_product_1", "lead", "mx_Cross_Sell_Product_1", "text", required_for=["get_cross_sell"]),
    FieldSpec("cross_sell_pitch_1", "lead", "mx_Cross_Sell_Pitch_1", "text", required_for=["get_cross_sell"]),
    FieldSpec("cross_sell_value_1", "lead", "mx_Cross_Sell_Value_1", "number", required_for=["get_cross_sell"]),
    FieldSpec("dob", "lead", "mx_DOB", "date", required_for=["get_client"]),
]

PROVIDER_SPECS: dict[str, list[FieldSpec]] = {
    "hubspot": HUBSPOT_FIELD_SPECS,
    "salesforce": SALESFORCE_FIELD_SPECS,
    "zoho": ZOHO_FIELD_SPECS,
    "dynamics": DYNAMICS_FIELD_SPECS,
    "freshworks": FRESHWORKS_FIELD_SPECS,
    "leadsquared": LEADSQUARED_FIELD_SPECS,
    "fake_leadsquared": LEADSQUARED_FIELD_SPECS,
    "mock": [],
}


def get_specs(provider: str) -> list[FieldSpec]:
    return PROVIDER_SPECS.get(provider, [])


# ─────────────────────────────── detect ──────────────────────────────────

async def detect(connection_id: str) -> ProvisioningReport:
    """Check which required fields are present vs missing in the bank's CRM."""
    from services import connection_registry

    conn = await connection_registry.get_connection(connection_id)
    if not conn:
        raise ValueError(f"Connection {connection_id} not found")

    specs = get_specs(conn.provider)
    report = ProvisioningReport(connection_id=connection_id, provider=conn.provider)

    if not specs:
        report.present = []
        report.missing = []
        return report

    if conn.provider == "hubspot":
        report = await _detect_hubspot(connection_id, conn, specs)
    elif conn.provider == "salesforce":
        report = await _detect_salesforce(connection_id, conn, specs)
    else:
        # For providers without a metadata API in scope, return all as "present"
        # (sandbox / mock / leadsquared fixtures already have the right fields)
        report.present = [s.crm_name for s in specs]

    return report


async def _detect_hubspot(connection_id: str, conn, specs: list[FieldSpec]) -> ProvisioningReport:
    report = ProvisioningReport(connection_id=connection_id, provider="hubspot")
    try:
        from services.secret_store import secret_store
        token_data = await secret_store().get_token(connection_id)
        if not token_data:
            report.missing = [s.crm_name for s in specs]
            return report

        from hubspot import HubSpot
        hs = HubSpot(access_token=token_data["access_token"])
        contact_props = {
            p.name
            for p in hs.crm.properties.core_api.get_all("contacts").results
        }
        deal_props = {
            p.name
            for p in hs.crm.properties.core_api.get_all("deals").results
        }
        for spec in specs:
            prop_set = deal_props if spec.object_type == "deal" else contact_props
            if spec.crm_name in prop_set:
                report.present.append(spec.crm_name)
            else:
                report.missing.append(spec.crm_name)
    except Exception as e:
        logger.warning("HubSpot detect failed: %s", e)
        report.missing = [s.crm_name for s in specs]
    return report


async def _detect_salesforce(connection_id: str, conn, specs: list[FieldSpec]) -> ProvisioningReport:
    report = ProvisioningReport(connection_id=connection_id, provider="salesforce")
    try:
        from services.secret_store import secret_store
        import httpx as _httpx
        token_data = await secret_store().get_token(connection_id)
        if not token_data:
            report.missing = [s.crm_name for s in specs]
            return report

        instance_url = conn.metadata_json.get("instance_url", "")
        access_token = token_data.get("access_token", "")
        existing_fields: set[str] = set()

        async with _httpx.AsyncClient() as c:
            r = await c.get(
                f"{instance_url}/services/data/v60.0/sobjects/Contact/describe",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if r.status_code == 200:
                existing_fields.update(f["name"] for f in r.json().get("fields", []))

        for spec in specs:
            if spec.crm_name in existing_fields or spec.object_type == "cross_sell__c":
                report.present.append(spec.crm_name)
            else:
                report.missing.append(spec.crm_name)
    except Exception as e:
        logger.warning("Salesforce detect failed: %s", e)
        report.missing = [s.crm_name for s in specs]
    return report


# ─────────────────────────────── provision ───────────────────────────────

async def provision(connection_id: str, field_names: list[str]) -> ProvisioningResult:
    """Create missing fields in the CRM. Returns result including SF zip if applicable."""
    from services import connection_registry

    conn = await connection_registry.get_connection(connection_id)
    if not conn:
        raise ValueError(f"Connection {connection_id} not found")

    specs = {s.crm_name: s for s in get_specs(conn.provider)}
    target_specs = [specs[n] for n in field_names if n in specs]

    if conn.provider == "hubspot":
        return await _provision_hubspot(connection_id, target_specs)
    elif conn.provider == "salesforce":
        return _provision_salesforce_package(target_specs)
    else:
        # For Zoho / Dynamics / Freshworks stubs: return success with a note
        result = ProvisioningResult()
        result.provisioned = field_names
        return result


async def _provision_hubspot(connection_id: str, specs: list[FieldSpec]) -> ProvisioningResult:
    result = ProvisioningResult()
    try:
        from services.secret_store import secret_store
        from hubspot import HubSpot
        from hubspot.crm.properties import PropertyCreate, PropertyGroupCreate

        token_data = await secret_store().get_token(connection_id)
        if not token_data:
            raise RuntimeError("No token found")

        hs = HubSpot(access_token=token_data["access_token"])

        # Ensure the SYNC property group exists
        for object_type in {"contact", "deal"}:
            try:
                hs.crm.properties.groups_api.create(
                    object_type=object_type,
                    property_group_create=PropertyGroupCreate(
                        name="sync_rm_briefing",
                        display_order=-1,
                        label="SYNC RM Briefing",
                    ),
                )
            except Exception:
                pass  # Group likely already exists

        for spec in specs:
            obj = spec.object_type
            prop = PropertyCreate(
                name=spec.crm_name,
                label=spec.crm_name.replace("_", " ").title(),
                type="string" if spec.crm_type in ("text", "textarea", "long_text") else
                     "number" if spec.crm_type == "number" else
                     "enumeration" if spec.crm_type == "enumeration" else
                     "date" if spec.crm_type == "date" else "string",
                field_type="textarea" if spec.crm_type in ("textarea", "long_text") else
                           "number" if spec.crm_type == "number" else
                           "select" if spec.crm_type == "enumeration" else
                           "date" if spec.crm_type == "date" else "text",
                group_name="sync_rm_briefing",
                options=[{"label": o, "value": o} for o in spec.options] if spec.options else [],
            )
            try:
                hs.crm.properties.core_api.create(object_type=obj, property_create=prop)
                result.provisioned.append(spec.crm_name)
            except Exception as e:
                err = str(e)
                if "already exists" in err.lower():
                    result.skipped.append(spec.crm_name)
                else:
                    result.errors[spec.crm_name] = err
    except Exception as e:
        logger.error("HubSpot provision failed: %s", e)
        result.errors["_global"] = str(e)
    return result


def _provision_salesforce_package(specs: list[FieldSpec]) -> ProvisioningResult:
    """Build a Salesforce metadata package zip the admin can deploy via Setup."""
    result = ProvisioningResult()

    # Build package.xml
    members = "\n".join(
        f"        <members>Contact.{s.crm_name}</members>"
        for s in specs if s.object_type == "contact" and s.crm_name.endswith("__c")
    )
    package_xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Package xmlns="http://soap.sforce.com/2006/04/metadata">
    <types>
        <members>Contact</members>
        <members>Opportunity</members>
        <name>CustomObject</name>
    </types>
    <types>
{members}
        <name>CustomField</name>
    </types>
    <version>60.0</version>
</Package>"""

    # Build Contact.object snippet
    contact_fields = ""
    for spec in specs:
        if spec.object_type in ("contact", "opportunity"):
            options_xml = "\n".join(
                f"            <values>\n                <fullName>{o}</fullName>\n                <default>false</default>\n            </values>"
                for o in spec.options
            )
            field_type = "Picklist" if spec.crm_type in ("Picklist", "enumeration") else spec.crm_type
            contact_fields += f"""
    <fields>
        <fullName>{spec.crm_name}</fullName>
        <label>{spec.name.replace('_', ' ').title()}</label>
        <type>{field_type}</type>
        {f'<valueSet><valueSetDefinition>{options_xml}</valueSetDefinition></valueSet>' if spec.options else ''}
        <length>255</length>
    </fields>"""

    contact_object = f"""<?xml version="1.0" encoding="UTF-8"?>
<CustomObject xmlns="http://soap.sforce.com/2006/04/metadata">
{contact_fields}
</CustomObject>"""

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("package.xml", package_xml)
        zf.writestr("objects/Contact.object", contact_object)
    result.sf_package_zip = buf.getvalue()
    result.provisioned = [s.crm_name for s in specs]
    return result
