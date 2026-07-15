"""OS-backed and in-memory secret storage for market-data API keys."""

from __future__ import annotations

import logging
from typing import Protocol

logger = logging.getLogger(__name__)

SERVICE_NAME = "GainGoblin"
SECRET_KEY_PREFIX = "market_data."


class SecretStore(Protocol):
    """Protocol for provider API-key storage."""

    def get_secret(self, provider_name: str) -> str | None:
        """Return the stored secret for ``provider_name``, or ``None``."""
        ...

    def set_secret(self, provider_name: str, value: str) -> None:
        """Persist ``value`` for ``provider_name``."""
        ...

    def delete_secret(self, provider_name: str) -> None:
        """Remove any stored secret for ``provider_name``."""
        ...


def _account_name(provider_name: str) -> str:
    normalized = str(provider_name or "").strip() or "unknown"
    return f"{SECRET_KEY_PREFIX}{normalized}"


class MemorySecretStore:
    """Session-only secret store used by tests and optional in-memory mode."""

    def __init__(self) -> None:
        self._secrets: dict[str, str] = {}

    def get_secret(self, provider_name: str) -> str | None:
        value = self._secrets.get(_account_name(provider_name))
        return value if value else None

    def set_secret(self, provider_name: str, value: str) -> None:
        cleaned = str(value or "").strip()
        if not cleaned:
            self.delete_secret(provider_name)
            return
        self._secrets[_account_name(provider_name)] = cleaned

    def delete_secret(self, provider_name: str) -> None:
        self._secrets.pop(_account_name(provider_name), None)

    def __repr__(self) -> str:
        return f"MemorySecretStore(entries={len(self._secrets)})"


class KeyringSecretStore:
    """Persist API keys through the operating-system credential store."""

    def __init__(self, service_name: str = SERVICE_NAME) -> None:
        self.service_name = service_name

    def get_secret(self, provider_name: str) -> str | None:
        try:
            import keyring
        except ImportError:
            logger.warning("keyring is unavailable; cannot read stored API key")
            return None
        try:
            value = keyring.get_password(self.service_name, _account_name(provider_name))
        except Exception:
            logger.exception("Failed to read API key from OS credential store")
            return None
        return value if value else None

    def set_secret(self, provider_name: str, value: str) -> None:
        cleaned = str(value or "").strip()
        if not cleaned:
            self.delete_secret(provider_name)
            return
        try:
            import keyring
        except ImportError as exc:
            raise RuntimeError("keyring package is required to save API keys") from exc
        try:
            keyring.set_password(self.service_name, _account_name(provider_name), cleaned)
        except Exception:
            logger.exception("Failed to save API key to OS credential store")
            raise

    def delete_secret(self, provider_name: str) -> None:
        try:
            import keyring
            from keyring.errors import PasswordDeleteError
        except ImportError:
            logger.warning("keyring is unavailable; cannot delete stored API key")
            return
        try:
            keyring.delete_password(self.service_name, _account_name(provider_name))
        except PasswordDeleteError:
            return
        except Exception:
            logger.exception("Failed to delete API key from OS credential store")
            raise

    def __repr__(self) -> str:
        return f"KeyringSecretStore(service_name={self.service_name!r})"
