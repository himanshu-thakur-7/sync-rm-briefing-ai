"""
CRM adapter factory — returns the correct adapter based on CRM_ADAPTER env var.
"""
from adapters.base import CRMAdapter
from config import settings


def get_crm_adapter() -> CRMAdapter:
    """Return the configured CRM adapter."""
    adapter_type = settings.crm_adapter.lower()

    if adapter_type == "mock":
        from adapters.mock_crm import MockCRMAdapter
        return MockCRMAdapter()
    elif adapter_type == "hubspot":
        from adapters.hubspot import HubSpotCRMAdapter
        return HubSpotCRMAdapter()
    elif adapter_type == "salesforce":
        from adapters.salesforce import SalesforceCRMAdapter
        return SalesforceCRMAdapter()
    else:
        raise ValueError(f"Unknown CRM adapter: {adapter_type}. Must be 'mock', 'hubspot', or 'salesforce'.")


# Singleton
_adapter: CRMAdapter | None = None


def crm() -> CRMAdapter:
    """Get the singleton CRM adapter instance."""
    global _adapter
    if _adapter is None:
        _adapter = get_crm_adapter()
    return _adapter
