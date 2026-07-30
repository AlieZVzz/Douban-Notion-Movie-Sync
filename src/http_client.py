"""Shared HTTP session helpers."""
from __future__ import annotations

from typing import Iterable

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

DEFAULT_RETRY_STATUSES = (429, 500, 502, 503, 504)


def create_retry_session(
    retries: int = 3,
    status_forcelist: Iterable[int] = DEFAULT_RETRY_STATUSES,
) -> requests.Session:
    """Create a requests session with connection pooling and bounded retries."""
    retry = Retry(
        total=retries,
        connect=retries,
        read=retries,
        status=retries,
        backoff_factor=0.8,
        status_forcelist=tuple(status_forcelist),
        # Writes are intentionally not retried: a lost response after a successful
        # Notion create-page call could otherwise create duplicate records.
        allowed_methods=frozenset({"GET"}),
        respect_retry_after_header=True,
        raise_on_status=False,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=10, pool_maxsize=10)
    session = requests.Session()
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
