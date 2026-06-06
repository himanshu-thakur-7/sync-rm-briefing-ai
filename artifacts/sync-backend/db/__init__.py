"""SYNC persistent-state layer.

SQLite via SQLModel + aiosqlite. Single-file DB at `sync.db`. Holds:
  - CRMConnection rows (one per bank+CRM pairing)
  - OAuthToken rows (encrypted via SecretStore, keyed by connection)
  - FieldMapping rows (per-connection canonical→bank-field overrides)
  - BriefingLogRow mirror of in-memory briefings
  - WebhookEvent lifecycle rows
  - ProvisioningStatus snapshots
  - CommandLog rows (Phase 6 voice commands)
"""
from db.engine import init_db, get_session, async_session_maker  # noqa: F401
