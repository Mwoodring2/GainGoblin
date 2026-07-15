"""Tests for market-data secret storage and settings migration."""

from __future__ import annotations

import json
import logging

from gaingoblin.logging_config import RedactingFilter, configure_logging, redact_text, redact_url
from gaingoblin.market_data.secret_store import MemorySecretStore
from gaingoblin.market_data.settings import (
    MASKED_API_KEY_PLACEHOLDER,
    MarketDataSettingsStore,
    mask_api_key,
)


def test_memory_secret_store_round_trip_and_clear() -> None:
    store = MemorySecretStore()
    store.set_secret("Alpha Vantage", "test-secret-key-12345")
    assert store.get_secret("Alpha Vantage") == "test-secret-key-12345"
    store.delete_secret("Alpha Vantage")
    assert store.get_secret("Alpha Vantage") is None


def test_secret_store_repr_does_not_expose_key() -> None:
    store = MemorySecretStore()
    store.set_secret("Alpha Vantage", "super-secret-value")
    assert "super-secret-value" not in repr(store)


def test_plaintext_api_key_migrates_into_secret_store_and_leaves_json(tmp_path) -> None:
    settings_path = tmp_path / "market_data_settings.json"
    settings_path.write_text(
        json.dumps(
            {
                "market_data_enabled": False,
                "selected_provider": "Alpha Vantage",
                "provider_api_key": "migrate-me-secret-key",
                "cache_duration_minutes": 7,
            },
            indent=2,
        ),
        encoding="utf-8",
    )
    secret_store = MemorySecretStore()
    store = MarketDataSettingsStore(settings_path, secret_store=secret_store)

    settings = store.load()

    assert settings.market_data_enabled is False
    assert settings.selected_provider == "Alpha Vantage"
    assert settings.cache_duration_minutes == 7
    assert store.last_migration_status == "succeeded"
    assert secret_store.get_secret("Alpha Vantage") == "migrate-me-secret-key"

    rewritten = json.loads(settings_path.read_text(encoding="utf-8"))
    assert "provider_api_key" not in rewritten
    assert "api_key" not in rewritten
    assert "migrate-me-secret-key" not in settings_path.read_text(encoding="utf-8")


def test_settings_save_never_writes_api_key(tmp_path) -> None:
    secret_store = MemorySecretStore()
    store = MarketDataSettingsStore(tmp_path / "settings.json", secret_store=secret_store)
    from gaingoblin.market_data.settings import MarketDataSettings

    store.save(
        MarketDataSettings(
            market_data_enabled=True,
            selected_provider="Alpha Vantage",
            cache_duration_minutes=9,
            api_key="should-not-persist",
        )
    )
    raw = json.loads((tmp_path / "settings.json").read_text(encoding="utf-8"))
    assert "provider_api_key" not in raw
    assert "api_key" not in raw
    assert "should-not-persist" not in json.dumps(raw)


def test_mask_api_key_uses_bullet_placeholder() -> None:
    assert mask_api_key("abcd1234") == MASKED_API_KEY_PLACEHOLDER
    assert "1234" not in mask_api_key("abcd1234")


def test_logging_never_contains_test_api_key(tmp_path, caplog) -> None:
    configure_logging(tmp_path / "logs")
    logger = logging.getLogger("gaingoblin.test_secrets")
    logger.addFilter(RedactingFilter())
    secret = "unit-test-api-key-SHOULD-NOT-APPEAR"
    with caplog.at_level(logging.INFO, logger="gaingoblin.test_secrets"):
        logger.info("api_key=%s provider=Alpha Vantage", secret)
        logger.info("url=%s", f"https://example.test/query?apikey={secret}&symbol=ORC")

    combined = "\n".join(record.getMessage() for record in caplog.records)
    assert secret not in combined
    assert "[REDACTED]" in combined
    assert secret not in redact_text(f"token={secret}")
    assert secret not in redact_url(f"https://example.test/?apikey={secret}")
