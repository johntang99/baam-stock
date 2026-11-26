"""Fetch public SEC filings for the extraction evaluation corpus (DP 1.18; D-32).

For each configured ticker: resolve the CIK from SEC's company_tickers.json, read the submissions JSON, take recent
8-K / 6-K filings, and download the press-release exhibits (EX-99.x) and the primary document. Raw files go to
data/corpus/sec/<TICKER>/<accession>/ (gitignored); data/labels/extraction-v0/manifest.jsonl (committed) records
url, sha256 of raw bytes and of the normalised text, so the corpus can be rebuilt and labels stay tied to a text.

Live use needs SEC_EDGAR_USER_AGENT ("<name> <contact email>", SEC fair-access policy) and stays <= 10 req/s.
  uv run python scripts/fetch_sec_corpus.py [--tickers NVDA,AMD] [--max 30] [--since 2023-01-01] [--archive DIR]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from datetime import date
from pathlib import Path
from typing import Any

from sr.config import load, repo_root
from sr.evidence.hashing import normalized_text, sha256_text
from sr.evidence.sources.transport import ArchiveTransport, LiveTransport, Transport

TICKERS_URL = "https://www.sec.gov/files/company_tickers.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik}.json"
INDEX_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}/index.json"
FILE_URL = "https://www.sec.gov/Archives/edgar/data/{cik_int}/{acc}/{name}"


def resolve_ciks(tr: Transport, tickers: list[str]) -> dict[str, str]:
    data = json.loads(tr.get(TICKERS_URL))
    by_ticker = {str(v["ticker"]).upper(): f"{int(v['cik_str']):010d}" for v in data.values()}
    missing = [t for t in tickers if t.upper() not in by_ticker]
    if missing:
        raise KeyError(f"tickers not in SEC company_tickers.json: {missing}")
    return {t: by_ticker[t.upper()] for t in tickers}


def pick_files(
    index: dict[str, Any], primary: str, patterns: list[str], include_primary: bool
) -> list[tuple[str, str]]:
    out = []
    for item in index.get("directory", {}).get("item", []):
        name = str(item.get("name", ""))
        low = re.sub(r"[^a-z0-9]", "", name.lower())
        if name.lower().endswith((".htm", ".html", ".txt")) and any(
            re.sub(r"[^a-z0-9]", "", p) in low for p in patterns
        ):
            out.append((name, "ex99"))
    if include_primary and primary and all(primary != n for n, _ in out):
        out.append((primary, "primary"))
    return out


def fetch(tr: Transport, tickers: list[str], since: date, max_per: int, corpus: Path, labels: Path) -> int:
    plan = load("extraction_eval")["corpus_plan"]["sec"]
    ciks = resolve_ciks(tr, tickers)
    manifest_path = labels / "manifest.jsonl"
    labels.mkdir(parents=True, exist_ok=True)
    existing = {}
    if manifest_path.exists():
        for line in manifest_path.read_text().splitlines():
            if line.strip():
                r = json.loads(line)
                existing[r["doc_key"]] = r
    added = 0
    for ticker, cik in ciks.items():
        sub = json.loads(tr.get(SUBMISSIONS_URL.format(cik=cik)))
        rec = sub.get("filings", {}).get("recent", {})
        taken = 0
        for i in range(len(rec.get("accessionNumber", []))):
            if taken >= max_per:
                break
            if rec["form"][i] not in plan["forms"] or date.fromisoformat(rec["filingDate"][i]) < since:
                continue
            acc = rec["accessionNumber"][i]
            nodash = acc.replace("-", "")
            index = json.loads(tr.get(INDEX_URL.format(cik_int=int(cik), acc=nodash)))
            files = pick_files(
                index, rec["primaryDocument"][i], plan["exhibit_patterns"], plan["include_primary_document"]
            )
            if not files:
                continue
            taken += 1
            for name, kind in files:
                key = f"{acc}:{name}"
                if key in existing:
                    continue
                url = FILE_URL.format(cik_int=int(cik), acc=nodash, name=name)
                raw = tr.get(url)
                rel = Path("sec") / ticker / acc / name
                (corpus / rel).parent.mkdir(parents=True, exist_ok=True)
                (corpus / rel).write_bytes(raw)
                ctype = "text/plain" if name.lower().endswith(".txt") else "text/html"
                text = normalized_text(raw, ctype)
                row = {
                    "doc_key": key,
                    "ticker": ticker,
                    "company_id": f"co_{ticker.lower()}",
                    "cik": cik,
                    "form": rec["form"][i],
                    "filing_date": rec["filingDate"][i],
                    "acceptance_datetime": rec.get("acceptanceDateTime", [None] * (i + 1))[i],
                    "file_kind": kind,
                    "url": url,
                    "path": rel.as_posix(),
                    "content_type": ctype,
                    "sha256_raw": hashlib.sha256(raw).hexdigest(),
                    "sha256_text": sha256_text(text),
                    "chars": len(text),
                }
                existing[key] = row
                added += 1
    manifest_path.write_text(
        "".join(json.dumps(existing[k], ensure_ascii=False, sort_keys=True) + "\n" for k in sorted(existing))
    )
    return added


def main() -> int:
    cfg = load("extraction_eval")
    plan = cfg["corpus_plan"]["sec"]
    ap = argparse.ArgumentParser()
    ap.add_argument("--tickers", default=",".join(plan["tickers"]))
    ap.add_argument("--max", type=int, default=int(plan["max_filings_per_company"]))
    ap.add_argument("--since", default=str(plan["since"]))
    ap.add_argument(
        "--archive", default="", help="read from an archive directory instead of the network (tests)"
    )
    a = ap.parse_args()
    tr: Transport = (
        ArchiveTransport(a.archive)
        if a.archive
        else LiveTransport(
            load("evidence")["sec_edgar"]["user_agent_env"],
            float(load("evidence")["sec_edgar"]["max_requests_per_s"]),
        )
    )
    root = repo_root()
    n = fetch(
        tr,
        [t.strip() for t in a.tickers.split(",") if t.strip()],
        date.fromisoformat(a.since),
        a.max,
        root / cfg["paths"]["corpus"],
        root / cfg["paths"]["labels"],
    )
    print(
        f"added {n} documents to {cfg['paths']['corpus']} (manifest: {cfg['paths']['labels']}/manifest.jsonl)"
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
