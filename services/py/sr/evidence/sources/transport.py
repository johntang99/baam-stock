"""HTTP transports: live (rate-limited, identified User-Agent) and archive (files on disk, for replay/tests)."""

from __future__ import annotations

import json
import os
import threading
import time
import urllib.request
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse


class Transport(Protocol):
    def get(self, url: str) -> bytes: ...

    def meta(self, url: str) -> dict[str, Any]: ...


class ArchiveTransport:
    """Maps https://host/path -> <root>/host/path. Optional sidecar <file>.meta.json holds capture metadata
    (e.g. {"received_at": "...Z"}) for arrival_mode=archived."""

    def __init__(self, root: str | Path) -> None:
        self.root = Path(root)

    def _path(self, url: str) -> Path:
        u = urlparse(url)
        p = (self.root / u.netloc / u.path.lstrip("/")).resolve()
        if self.root.resolve() not in p.parents:
            raise ValueError(f"archive path escapes root: {url}")
        return p

    def get(self, url: str) -> bytes:
        p = self._path(url)
        if not p.exists():
            raise FileNotFoundError(f"not in archive: {url}")
        return p.read_bytes()

    def meta(self, url: str) -> dict[str, Any]:
        m = self._path(url).with_name(self._path(url).name + ".meta.json")
        return json.loads(m.read_text()) if m.exists() else {}


class LiveTransport:
    """Live HTTP GET with a minimum interval between requests. The User-Agent must identify the operator
    (SEC fair-access policy); it is read from the environment and never hard-coded."""

    def __init__(self, user_agent_env: str, max_requests_per_s: float, timeout_s: float = 30.0) -> None:
        ua = os.environ.get(user_agent_env, "").strip()
        if not ua or "example.com" in ua:
            raise RuntimeError(f"set {user_agent_env} to an identifying User-Agent before live polling")
        self._ua = ua
        self._min_interval = 1.0 / max_requests_per_s
        self._timeout = timeout_s
        self._lock = threading.Lock()
        self._last = 0.0

    def get(self, url: str) -> bytes:
        with self._lock:
            wait = self._last + self._min_interval - time.monotonic()
            if wait > 0:
                time.sleep(wait)
            self._last = time.monotonic()
        req = urllib.request.Request(url, headers={"User-Agent": self._ua, "Accept-Encoding": "identity"})
        with urllib.request.urlopen(req, timeout=self._timeout) as r:  # noqa: S310 (https URLs from config)
            data: bytes = r.read()
            return data

    def meta(self, url: str) -> dict[str, Any]:
        return {}
