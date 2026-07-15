"""User-safe market-data error types.

Messages must never include API keys, tokens, or raw provider payloads.
"""

from __future__ import annotations


class MarketDataError(RuntimeError):
    """Base market-data failure with a stable user-facing message."""

    user_message = "Market data provider is unavailable."

    def __str__(self) -> str:
        return self.user_message

    def __repr__(self) -> str:
        return f"{self.__class__.__name__}()"


class MarketDataDisabledError(MarketDataError):
    user_message = "Online market data is disabled. Enable it before fetching market numbers."


class MissingApiKeyError(MarketDataError):
    user_message = "API key is missing."


class ProviderNotConfiguredError(MarketDataError):
    user_message = "Provider is not configured."


class ProviderUnavailableError(MarketDataError):
    user_message = "Market data provider is unavailable."


class AuthenticationError(MarketDataError):
    user_message = "Market data authentication failed."


class SymbolNotFoundError(MarketDataError):
    user_message = "Symbol was not found."


class RateLimitError(MarketDataError):
    user_message = "Provider rate limit was reached."


class NoMarketDataError(MarketDataError):
    user_message = "No historical data was returned."


class NetworkUnavailableError(MarketDataError):
    user_message = "Internet connection failed."


class ProviderTimeoutError(MarketDataError):
    user_message = "Provider request timed out."


class MalformedMarketDataError(MarketDataError):
    user_message = "Market data provider returned data Gain Goblin could not read."


class RealtimeNotAvailableError(MarketDataError):
    user_message = "Your provider plan does not include real-time data."
