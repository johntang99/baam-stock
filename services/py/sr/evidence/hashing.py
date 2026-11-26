"""Content hashing for idempotent ingestion (DC §3.2 UQ (doc_id, content_hash))."""

from __future__ import annotations

import hashlib
import html
import re

_TAG = re.compile(r"<[^>]+>")
_WS = re.compile(r"\s+")


def normalized_text(content: bytes, content_type: str) -> str:
    text = content.decode("utf-8", errors="replace")
    if "html" in content_type:
        text = html.unescape(_TAG.sub(" ", text))
    return _WS.sub(" ", text).strip()


def content_hash(content: bytes, content_type: str, normalize: bool = True) -> str:
    data = normalized_text(content, content_type).encode() if normalize else content
    return hashlib.sha256(data).hexdigest()


def sha256_text(s: str) -> str:
    return hashlib.sha256(s.encode()).hexdigest()
