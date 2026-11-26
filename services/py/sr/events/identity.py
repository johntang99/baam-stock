"""Stable event identity keys (DC §3.4 events.identity_key). Same real-world event => same key, so repeated
or re-published news merges into one event instead of creating duplicates."""

from __future__ import annotations

import re
from datetime import date

_SAFE = re.compile(r"[^a-z0-9._-]+")


def _norm(part: str) -> str:
    s = _SAFE.sub("-", part.strip().lower()).strip("-")
    if not s:
        raise ValueError(f"empty identity component from {part!r}")
    return s


def earnings_key(company_id: str, fiscal_period: str) -> str:
    if not re.fullmatch(r"FY\d{4}(Q[1-4])?", fiscal_period.strip().upper()):
        raise ValueError(f"fiscal_period must look like FY2027Q3, got {fiscal_period!r}")
    return f"earnings:{_norm(company_id)}:{fiscal_period.strip().upper()}"


def policy_key(agency: str, document_no: str) -> str:
    return f"policy:{agency.strip().upper()}:{_norm(document_no)}"


def case_key(court: str, docket: str) -> str:
    return f"case:{_norm(court)}:{_norm(docket)}"


def deal_key(acquirer_company_id: str, target_company_id: str, agreement_date: date) -> str:
    return f"deal:{_norm(acquirer_company_id)}:{_norm(target_company_id)}:{agreement_date.isoformat()}"


def management_key(company_id: str, role: str, effective: date) -> str:
    return f"mgmt:{_norm(company_id)}:{_norm(role)}:{effective.isoformat()}"


def validate(key: str) -> str:
    if not re.fullmatch(r"(earnings|policy|case|deal|mgmt):[A-Za-z0-9:._-]+", key):
        raise ValueError(f"invalid identity_key {key!r}")
    return key
