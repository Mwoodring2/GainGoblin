"""Shared HTTP helpers for market-data providers."""

from __future__ import annotations

import json
import logging
import socket
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from gaingoblin.logging_config import redact_url
from gaingoblin.market_data.errors import (
    AuthenticationError,
    MalformedMarketDataError,
    NetworkUnavailableError,
    ProviderTimeoutError,
    RateLimitError,
)

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT_SECONDS = 15.0
USER_AGENT = "GainGoblin/0.1.8-alpha (+https://github.com/local/GainGoblin)"


def get_json(
    url: str,
    *,
    params: dict[str, str] | None = None,
    timeout_seconds: float = DEFAULT_TIMEOUT_SECONDS,
    headers: dict[str, str] | None = None,
) -> Any:
    """GET JSON from ``url`` with an explicit timeout.

    Query values may include secrets; they are never logged.
    """
    query = urlencode(params or {})
    full_url = f"{url}?{query}" if query else url
    request_headers = {"User-Agent": USER_AGENT, "Accept": "application/json"}
    if headers:
        request_headers.update(headers)
    request = Request(full_url, headers=request_headers, method="GET")
    safe_url = redact_url(full_url)
    logger.debug("market_data_http_get url=%s", safe_url)

    try:
        with urlopen(request, timeout=timeout_seconds) as response:
            status = getattr(response, "status", None) or response.getcode()
            body = response.read()
    except HTTPError as exc:
        if exc.code in {401, 403}:
            raise AuthenticationError() from exc
        if exc.code == 429:
            raise RateLimitError() from exc
        logger.info("market_data_http_error status=%s url=%s", exc.code, safe_url)
        raise NetworkUnavailableError() from exc
    except TimeoutError as exc:
        raise ProviderTimeoutError() from exc
    except URLError as exc:
        reason = exc.reason
        if isinstance(reason, (TimeoutError, socket.timeout)):
            raise ProviderTimeoutError() from exc
        reason_text = str(reason).lower()
        if "timed out" in reason_text or "timeout" in reason_text:
            raise ProviderTimeoutError() from exc
        logger.info("market_data_http_network_error url=%s", safe_url)
        raise NetworkUnavailableError() from exc
    except OSError as exc:
        logger.info("market_data_http_os_error url=%s", safe_url)
        raise NetworkUnavailableError() from exc

    if status is not None and int(status) >= 400:
        if int(status) in {401, 403}:
            raise AuthenticationError()
        if int(status) == 429:
            raise RateLimitError()
        raise NetworkUnavailableError()

    try:
        text = body.decode("utf-8")
        return json.loads(text)
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise MalformedMarketDataError() from exc
