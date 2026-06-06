"""Encrypted secret storage for OAuth tokens.

The default implementation uses Fernet (AES128-CBC + HMAC-SHA256) with a key
read from `settings.secret_key`. If no key is set, one is generated on first
boot and persisted to `.secret.key` next to the working directory. Swap to a
VaultSecretStore / SecretsManagerSecretStore in production by changing the
factory.
"""
from __future__ import annotations

import json
import logging
import os
from abc import ABC, abstractmethod
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from cryptography.fernet import Fernet, InvalidToken
from sqlmodel import select

from config import settings
from db import get_session
from db.models import OAuthToken

logger = logging.getLogger(__name__)

_SECRET_KEY_FILE = Path(".secret.key")


def _ensure_key() -> bytes:
    """Resolve the Fernet key, generating + persisting one if missing."""
    if settings.secret_key:
        return settings.secret_key.encode() if isinstance(settings.secret_key, str) else settings.secret_key
    if _SECRET_KEY_FILE.exists():
        return _SECRET_KEY_FILE.read_bytes().strip()
    key = Fernet.generate_key()
    _SECRET_KEY_FILE.write_bytes(key)
    try:
        os.chmod(_SECRET_KEY_FILE, 0o600)
    except OSError:
        pass
    logger.warning(
        "Generated a new Fernet key at %s. Set SECRET_KEY in env to make this deterministic across restarts.",
        _SECRET_KEY_FILE.absolute(),
    )
    return key


class SecretStore(ABC):
    @abstractmethod
    async def get_token(self, connection_id: str) -> Optional[dict]:
        ...

    @abstractmethod
    async def put_token(self, connection_id: str, token: dict) -> None:
        ...

    @abstractmethod
    async def delete_token(self, connection_id: str) -> None:
        ...


class FernetSecretStore(SecretStore):
    """DB-backed encrypted store. Tokens live in the `oauth_tokens` table."""

    def __init__(self, key: Optional[bytes] = None) -> None:
        self._fernet = Fernet(key or _ensure_key())

    async def get_token(self, connection_id: str) -> Optional[dict]:
        async with get_session() as session:
            row = (
                await session.exec(
                    select(OAuthToken).where(OAuthToken.connection_id == connection_id)
                )
            ).first()
            if row is None:
                return None
            try:
                return json.loads(self._fernet.decrypt(row.encrypted_blob).decode())
            except InvalidToken:
                logger.error("Token for connection %s could not be decrypted; key mismatch?", connection_id)
                return None

    async def put_token(self, connection_id: str, token: dict) -> None:
        blob = self._fernet.encrypt(json.dumps(token).encode())
        expires_at: Optional[datetime] = None
        if isinstance(token.get("expires_at"), (int, float)):
            expires_at = datetime.fromtimestamp(token["expires_at"], tz=timezone.utc)
        async with get_session() as session:
            existing = (
                await session.exec(
                    select(OAuthToken).where(OAuthToken.connection_id == connection_id)
                )
            ).first()
            if existing is None:
                session.add(
                    OAuthToken(
                        connection_id=connection_id,
                        encrypted_blob=blob,
                        expires_at=expires_at,
                        refreshed_at=datetime.now(timezone.utc),
                    )
                )
            else:
                existing.encrypted_blob = blob
                existing.expires_at = expires_at
                existing.refreshed_at = datetime.now(timezone.utc)
                session.add(existing)

    async def delete_token(self, connection_id: str) -> None:
        async with get_session() as session:
            existing = (
                await session.exec(
                    select(OAuthToken).where(OAuthToken.connection_id == connection_id)
                )
            ).first()
            if existing is not None:
                await session.delete(existing)


_store: Optional[SecretStore] = None


def secret_store() -> SecretStore:
    global _store
    if _store is None:
        _store = FernetSecretStore()
    return _store
