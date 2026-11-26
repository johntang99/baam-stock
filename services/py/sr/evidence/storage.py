"""Raw document store. Local directory now (data/evidence, gitignored); Supabase Storage later (same paths)."""

from __future__ import annotations

from pathlib import Path

from sr.config import load, repo_root

_EXT = {"text/html": "html", "text/plain": "txt", "application/json": "json", "application/pdf": "pdf"}


class LocalDocStorage:
    def __init__(self, root: str | Path | None = None) -> None:
        self.root = Path(root) if root else repo_root() / load("evidence")["storage"]["root"]

    def put(self, source_id: str, doc_id: str, version: int, content: bytes, content_type: str) -> str:
        rel = Path(source_id) / doc_id / f"v{version}.{_EXT.get(content_type, 'bin')}"
        p = self.root / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        if not p.exists():  # write-once
            p.write_bytes(content)
        return rel.as_posix()

    def get(self, rel_path: str) -> bytes:
        return (self.root / rel_path).read_bytes()
