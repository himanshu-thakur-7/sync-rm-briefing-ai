"""Provisioning service tests.

Tests that:
- PROVIDER_SPECS contains entries for all known providers
- _provision_salesforce_package() returns a non-empty zip with package.xml
- FieldSpec dataclass is correctly structured
"""
import io
import zipfile
import pytest
from services.provisioning import (
    PROVIDER_SPECS,
    FieldSpec,
    _provision_salesforce_package,
    get_specs,
)


def test_all_providers_have_specs():
    """Every real CRM provider has at least one FieldSpec."""
    real_providers = ["hubspot", "salesforce", "zoho", "dynamics", "freshworks", "leadsquared"]
    for provider in real_providers:
        specs = get_specs(provider)
        assert specs, f"No specs for {provider}"


def test_field_spec_structure():
    """FieldSpecs have non-empty required fields."""
    specs = get_specs("hubspot")
    for spec in specs:
        assert spec.name, "FieldSpec.name is empty"
        assert spec.crm_name, "FieldSpec.crm_name is empty"
        assert spec.object_type, "FieldSpec.object_type is empty"
        assert spec.required_for, "FieldSpec.required_for is empty"


def test_salesforce_package_zip_structure():
    """The SF package zip must be non-empty and contain package.xml."""
    specs = get_specs("salesforce")
    result = _provision_salesforce_package(specs)

    assert result.sf_package_zip, "sf_package_zip is empty"
    assert len(result.provisioned) > 0, "No fields marked as provisioned"

    buf = io.BytesIO(result.sf_package_zip)
    with zipfile.ZipFile(buf, "r") as zf:
        names = zf.namelist()
        assert "package.xml" in names, f"package.xml missing; found: {names}"
        pkg = zf.read("package.xml").decode()
        assert "CustomField" in pkg or "CustomObject" in pkg


def test_fake_leadsquared_specs_match_fixtures():
    """FakeLeadSquared specs match the fields present in the fixture JSON files."""
    import json
    from pathlib import Path

    fixture = json.loads(
        (Path(__file__).parent.parent / "adapters/fixtures/leadsquared/leads.json").read_text()
    )
    fixture_fields = {f["SchemaName"] for lead in fixture for f in lead.get("Fields", [])}
    specs = get_specs("fake_leadsquared")
    for spec in specs:
        if spec.object_type == "lead":
            assert spec.crm_name in fixture_fields, \
                f"Spec field {spec.crm_name} not in LSQ fixture (add it or remove the spec)"
