"""Step 1 collection log (DP 1.27; D-45; AC-56): every item retrieved by a run is recorded — including those not used.

Dispositions (DC §3.2): kept | duplicate (same normalised content seen earlier, duplicate_of the first item) |
excluded_irrelevant | excluded_after_asof (available after the run's as_of; used next run) | excluded_restricted
(restricted review; placeholder only) | pending_review (low-confidence category) | fetch_failed.
Decisions depend only on content hashes and availability times, so replaying the same window yields the same set.
Counts are aggregated from the items, never hand-filled.
"""

from __future__ import annotations

import json
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from sr.config import load
from sr.db import Conn, jsonb
from sr.evidence.classify import classify
from sr.evidence.hashing import normalized_text
from sr.evidence.ingest import ingest
from sr.evidence.sources.base import EvidenceSource, FetchFailure, RawDocument
from sr.evidence.storage import LocalDocStorage
from sr.ids import new_id
from sr.timeguard import ensure_utc

RESTRICTED_PLACEHOLDER = "［受限材料：合规复核中，内容不显示］"


@dataclass(frozen=True)
class CollectionResult:
    collection_run_id: str
    counts: dict[str, Any]
    item_ids: list[str]


def _peers(conn: Conn, security_id: str) -> set[str]:
    rows = conn.execute(
        """select s2.company_id from securities s
           join benchmark_versions bv on bv.benchmark_id = s.primary_benchmark_id
           cross join lateral jsonb_array_elements(bv.constituents) c
           join securities s2 on s2.security_id = c->>'security_id'
           where s.security_id = %s""",
        (security_id,),
    ).fetchall()
    return {r["company_id"] for r in rows}


def _topic_linked(conn: Conn, raw: RawDocument, text: str, security_id: str) -> bool:
    if raw.content_type != "application/json":
        return False
    from sr.events.policy import _template, match_topics

    try:
        rec = json.loads(text)
    except json.JSONDecodeError:
        return False
    found = _template(rec)
    if not found:
        return False
    _, tpl = found
    return any(
        lk["security_id"] == security_id for t in match_topics(rec, tpl) for lk in tpl["topics"][t]["links"]
    )


def counts_from_items(items: list[dict[str, Any]]) -> dict[str, Any]:
    disp = Counter(i["disposition"] for i in items)
    matrix: dict[str, dict[str, int]] = defaultdict(dict)
    for i in items:
        matrix[i["channel"]][i["category"]] = matrix[i["channel"]].get(i["category"], 0) + 1
    return {
        "fetched": len(items),
        "kept": disp["kept"],
        "duplicate": disp["duplicate"],
        "excluded": disp["excluded_irrelevant"] + disp["excluded_after_asof"] + disp["excluded_restricted"],
        "excluded_irrelevant": disp["excluded_irrelevant"],
        "excluded_after_asof": disp["excluded_after_asof"],
        "excluded_restricted": disp["excluded_restricted"],
        "pending_review": disp["pending_review"],
        "failed": disp["fetch_failed"],
        "by_channel": dict(Counter(i["channel"] for i in items)),
        "by_category": dict(Counter(i["category"] for i in items)),
        "matrix": {k: dict(v) for k, v in matrix.items()},
    }


def run_collection(
    conn: Conn,
    security_id: str,
    sources: list[EvidenceSource],
    window_from: datetime,
    as_of: datetime,
    storage: LocalDocStorage | None = None,
    pipeline_run_id: str | None = None,
    snapshot_id: str | None = None,
    market_summary: dict[str, Any] | None = None,
    now: datetime | None = None,
) -> CollectionResult:
    cfg = load("collection")
    wf = ensure_utc(window_from, "window_from").to_pydatetime()
    asof = ensure_utc(as_of, "as_of").to_pydatetime()
    started = ensure_utc(now or datetime.now(UTC), "now").to_pydatetime()
    storage = storage or LocalDocStorage()
    sec = conn.execute("select company_id from securities where security_id = %s", (security_id,)).fetchone()
    if sec is None:
        raise KeyError(security_id)
    target_co = sec["company_id"]
    peers = _peers(conn, security_id) - {target_co}
    run_id = (
        f"col_{security_id.removeprefix('sec_')}_{asof.strftime('%Y%m%d_%H%M%S')}_{new_id('x')[-6:].lower()}"
    )
    conn.execute(
        """insert into collection_runs (collection_run_id, pipeline_run_id, snapshot_id, security_id, window_from,
             window_to, sources_polled, counts, started_at) values (%s,%s,%s,%s,%s,%s,'[]','{}',%s)""",
        (run_id, pipeline_run_id, snapshot_id, security_id, wf, asof, started),
    )

    polled: list[dict[str, Any]] = []
    fetched: list[RawDocument] = []
    failures: list[FetchFailure] = []
    for src in sources:
        kind = conn.execute("select kind from data_sources where source_id = %s", (src.source_id,)).fetchone()
        channel = cfg["channel_by_source_kind"][kind["kind"]] if kind else "news_wire"
        t0 = datetime.now(UTC)
        try:
            docs = src.poll(wf)
            fails = list(getattr(src, "failures", []))
            status = "ok"
        except TimeoutError:
            docs, fails, status = [], [], "timeout"
        except Exception:  # noqa: BLE001 - a broken source must not stop the run; recorded as error
            docs, fails, status = [], [], "error"
        fetched += docs
        failures += fails
        polled.append(
            {
                "source_id": src.source_id,
                "channel": channel,
                "status": status,
                "items_fetched": len(docs) + len(fails),
                "latency_ms": int((datetime.now(UTC) - t0).total_seconds() * 1000),
            }
        )

    rows: list[dict[str, Any]] = []
    for raw in fetched:
        res = ingest(conn, raw, now=raw.available_at or started, storage=storage)
        v = conn.execute(
            """select v.*, d.subject_company_ids, ds.kind from source_document_versions v join source_documents d using (doc_id)
               join data_sources ds on ds.source_id = d.source_id where v.doc_version_id = %s""",
            (res.doc_version_id,),
        ).fetchone()
        assert v is not None
        text = normalized_text(raw.content, raw.content_type)
        cl = classify(
            f"{raw.title}\n{text}",
            v["kind"],
            list(v["subject_company_ids"]),
            target_co,
            peers,
            _topic_linked(conn, raw, raw.content.decode(errors="replace"), security_id),
        )
        eff = v["simulated_available_at"] or v["available_at"]
        rows.append({"raw": raw, "v": v, "cl": cl, "eff": eff, "text": text})

    # first occurrence of each content hash inside the window (by availability, then external_ref) is the original
    order = sorted(
        range(len(rows)),
        key=lambda i: (rows[i]["eff"], rows[i]["raw"].source_id, rows[i]["raw"].external_ref),
    )
    first_by_hash: dict[str, int] = {}
    items: list[dict[str, Any]] = []
    for i in order:
        r = rows[i]
        v, cl, raw = r["v"], r["cl"], r["raw"]
        item_id = new_id("ci")
        r["item_id"] = item_id
        disposition, duplicate_of, reason = "kept", None, None
        if v["visibility"] == "restricted_review":
            disposition, reason = "excluded_restricted", "restricted_review"
        elif r["eff"] > asof:
            disposition, reason = "excluded_after_asof", f"available {r['eff'].isoformat()} > as_of"
        elif v["content_hash"] in first_by_hash:
            disposition, duplicate_of = "duplicate", rows[first_by_hash[v["content_hash"]]]["item_id"]
        elif cl.relevance < float(cfg["relevance"]["keep_threshold"]):
            disposition, reason = "excluded_irrelevant", cl.reason
        elif cl.category_confidence < float(cfg["category_min_confidence"]):
            disposition, reason = "pending_review", "low_category_confidence"
        if (
            disposition in ("kept", "pending_review", "excluded_irrelevant")
            and v["content_hash"] not in first_by_hash
        ):
            first_by_hash[v["content_hash"]] = i
        restricted = disposition == "excluded_restricted"
        items.append(
            {
                "item_id": item_id,
                "collection_run_id": run_id,
                "source_id": raw.source_id,
                "channel": cl.channel,
                "category": cl.category,
                "category_confidence": cl.category_confidence,
                "title": RESTRICTED_PLACEHOLDER if restricted else raw.title,
                "snippet": None if restricted else r["text"][: int(cfg["snippet_chars"])],
                "doc_version_id": v["doc_version_id"],
                "mentions": list(cl.mentions),
                "disposition": disposition,
                "duplicate_of": duplicate_of,
                "exclusion_reason": reason,
                "relevance": cl.relevance,
                "source_published_at": v["source_published_at"],
                "source_published_precision": v["source_published_precision"],
                "received_at": v["received_at"],
                "available_at": r["eff"],
            }
        )
    for f in failures:
        kind = conn.execute("select kind from data_sources where source_id = %s", (f.source_id,)).fetchone()
        items.append(
            {
                "item_id": new_id("ci"),
                "collection_run_id": run_id,
                "source_id": f.source_id,
                "channel": cfg["channel_by_source_kind"][kind["kind"]] if kind else "news_wire",
                "category": "other",
                "category_confidence": None,
                "title": f.title,
                "snippet": None,
                "doc_version_id": None,
                "mentions": [],
                "disposition": "fetch_failed",
                "duplicate_of": None,
                "exclusion_reason": f"{f.error}: {f.url}",
                "relevance": None,
                "source_published_at": None,
                "source_published_precision": None,
                "received_at": None,
                "available_at": None,
            }
        )
    if market_summary is not None:  # market data is logged as one summary item, never per quote (DC §3.2)
        items.append(
            {
                "item_id": new_id("ci"),
                "collection_run_id": run_id,
                "source_id": market_summary["source_id"],
                "channel": "market_data",
                "category": "market_data",
                "category_confidence": 1.0,
                "title": "行情汇总",
                "snippet": json.dumps(
                    {k: v for k, v in market_summary.items() if k != "source_id"}, default=str, sort_keys=True
                ),
                "doc_version_id": None,
                "mentions": [target_co],
                "disposition": "kept",
                "duplicate_of": None,
                "exclusion_reason": None,
                "relevance": 1.0,
                "source_published_at": None,
                "source_published_precision": None,
                "received_at": asof,
                "available_at": asof,
            }
        )

    for it in items:  # originals before duplicates (duplicate_of FK)
        it["linked_evidence_ids"] = []
    for it in sorted(items, key=lambda x: x["disposition"] == "duplicate"):
        cols = list(it)
        conn.execute(
            f"insert into collection_items ({', '.join(cols)}) values ({', '.join(['%s'] * len(cols))})",
            [it[c] for c in cols],
        )
    counts = counts_from_items(items)
    conn.execute(
        "update collection_runs set sources_polled = %s, counts = %s, finished_at = %s where collection_run_id = %s",
        (jsonb(polled), jsonb(counts), datetime.now(UTC) if now is None else started, run_id),
    )
    return CollectionResult(run_id, counts, [i["item_id"] for i in items])


def link_items(conn: Conn, doc_version_id: str, event_id: str, evidence_ids: list[str]) -> int:
    """Record which event/evidence used the kept items of a document version (append-only links)."""
    rows = conn.execute(
        """update collection_items set linked_event_id = coalesce(linked_event_id, %s),
             linked_evidence_ids = (select array(select distinct unnest(linked_evidence_ids || %s::text[])))
           where doc_version_id = %s and disposition = 'kept' and (linked_event_id is null or linked_event_id = %s)
           returning item_id""",
        (event_id, evidence_ids, doc_version_id, event_id),
    ).fetchall()
    return len(rows)
