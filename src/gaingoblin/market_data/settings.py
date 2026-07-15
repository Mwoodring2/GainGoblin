"""Non-secret market-data settings stored as local JSON."""

from __future__ import annotations

import json
import logging
from dataclasses import asdict, dataclass
from pathlib import Path

from gaingoblin.market_data.secret_store import KeyringSecretStore, MemorySecretStore, SecretStore

logger = logging.getLogger(__name__)

MASKED_API_KEY_PLACEHOLDER = "••••••••"


@dataclass(frozen=True, slots=True, init=False)
class MarketDataSettings:
    """Non-secret Market Data Scout preferences."""

    market_data_enabled: bool
    selected_provider: str
    cache_duration_minutes: int

    def __init__(
        self,
        market_data_enabled: bool = False,
        selected_provider: str = "Alpha Vantage",
        cache_duration_minutes: int = 5,
        *,
        enabled: bool | None = None,
        provider_name: str | None = None,
        provider_api_key: str | None = None,
        api_key: str | None = None,
        prefer_realtime: bool | None = None,
    ) -> None:
        if enabled is not None:
            market_data_enabled = enabled
        if provider_name is not None:
            selected_provider = provider_name
        # Legacy kwargs accepted but ignored — secrets live in SecretStore.
        _ = provider_api_key
        _ = api_key
        _ = prefer_realtime
        object.__setattr__(self, "market_data_enabled", bool(market_data_enabled))
        object.__setattr__(self, "selected_provider", str(selected_provider or "Alpha Vantage"))
        object.__setattr__(self, "cache_duration_minutes", max(1, int(cache_duration_minutes)))

    @property
    def enabled(self) -> bool:
        return self.market_data_enabled

    @property
    def provider_name(self) -> str:
        return self.selected_provider

    @property
    def prefer_realtime(self) -> bool:
        return False


class MarketDataSettingsStore:
    """Load and save non-secret settings; migrate plaintext API keys once."""

    def __init__(
        self,
        path: Path,
        secret_store: SecretStore | None = None,
    ) -> None:
        self.path = Path(path)
        self.secret_store: SecretStore = secret_store or KeyringSecretStore()
        self.last_migration_status: str | None = None

    @classmethod
    def default(cls) -> MarketDataSettingsStore:
        return cls(Path("data") / "market_data_settings.json")

    def load(self) -> MarketDataSettings:
        if not self.path.exists():
            return MarketDataSettings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError, TypeError, ValueError):
            return MarketDataSettings()

        settings = MarketDataSettings(
            market_data_enabled=bool(raw.get("market_data_enabled", raw.get("enabled", False))),
            selected_provider=str(raw.get("selected_provider", raw.get("provider_name", "Alpha Vantage"))),
            cache_duration_minutes=max(1, int(raw.get("cache_duration_minutes", 5))),
        )
        if settings.selected_provider not in {"Alpha Vantage", "Mock"}:
            settings = MarketDataSettings(
                market_data_enabled=settings.market_data_enabled,
                selected_provider="Alpha Vantage",
                cache_duration_minutes=settings.cache_duration_minutes,
            )
        self._migrate_plaintext_api_key(raw, settings)
        return settings

    def save(self, settings: MarketDataSettings) -> None:
        payload = asdict(settings)
        # Never persist API keys in settings JSON.
        payload.pop("provider_api_key", None)
        payload.pop("api_key", None)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps(payload, indent=2), encoding="utf-8")

    def _migrate_plaintext_api_key(self, raw: dict, settings: MarketDataSettings) -> None:
        plaintext = raw.get("provider_api_key", raw.get("api_key", ""))
        has_plaintext_field = "provider_api_key" in raw or "api_key" in raw
        if not plaintext:
            if has_plaintext_field:
                try:
                    self.save(settings)
                    self.last_migration_status = "stripped_empty"
                    logger.info(
                        "Removed empty plaintext API key field from settings provider=%s",
                        settings.selected_provider,
                    )
                except OSError:
                    self.last_migration_status = "failed"
                    logger.exception("Failed to rewrite settings without empty API key field")
            return

        try:
            self.secret_store.set_secret(settings.selected_provider, str(plaintext))
            self.save(settings)
            self.last_migration_status = "succeeded"
            logger.info(
                "Migrated plaintext API key into SecretStore provider=%s",
                settings.selected_provider,
            )
        except Exception:
            self.last_migration_status = "failed"
            logger.exception(
                "Failed to migrate plaintext API key into SecretStore provider=%s",
                settings.selected_provider,
            )


def mask_api_key(api_key: str) -> str:
    """Return a masked placeholder; never reveal characters from the key."""
    if not api_key:
        return ""
    return MASKED_API_KEY_PLACEHOLDER


def default_secret_store(*, memory: bool = False) -> SecretStore:
    """Return the process secret store used by the application."""
    if memory:
        return MemorySecretStore()
    return KeyringSecretStore()
