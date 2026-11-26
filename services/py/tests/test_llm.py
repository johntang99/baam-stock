"""DP 1.05: LLM providers — quotes verified against the source, every call logged, no tools, refusals handled.
No network: the Claude provider is exercised with a stub client."""

import json
from types import SimpleNamespace
from typing import Any

import pytest

from sr.llm import get_provider
from sr.llm.anthropic import ClaudeProvider
from sr.llm.base import FACTS_SCHEMA, ListCallLogger
from sr.llm.fake import FakeLLMProvider

DOC = (
    "Synthetic Semiconductor Co announced results. Revenue for the quarter was $35.1 billion, up 12%. "
    "GAAP gross margin was 74.6%."
)


def test_default_provider_is_fake(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_PROVIDER", raising=False)
    assert isinstance(get_provider(), FakeLLMProvider)


def test_fake_extracts_with_verified_spans() -> None:
    log = ListCallLogger()
    r = FakeLLMProvider(logger=log).extract_facts(DOC, "docv_x")
    assert r.status == "succeeded" and {f.metric for f in r.facts} == {"revenue", "gross_margin"}
    rev = next(f for f in r.facts if f.metric == "revenue")
    assert rev.value == 35.1 and rev.unit == "USD_billion"
    assert DOC[rev.span["char_start"] : rev.span["char_end"]] == rev.quote
    (rec,) = log.records
    assert rec.call_id == r.call_id and rec.request_params["tools"] == [] and rec.doc_version_id == "docv_x"
    assert len(rec.prompt_hash) == 64 and len(rec.input_hash) == 64


def test_hallucinated_quote_rejects_the_whole_call() -> None:
    p = FakeLLMProvider()
    p.register(
        DOC,
        [
            {
                "metric": "revenue",
                "value": 35.1,
                "unit": "USD_billion",
                "currency": "USD",
                "period": None,
                "basis": None,
                "quote": "Revenue for the quarter was $35.1 billion",
            },
            {
                "metric": "eps",
                "value": 0.81,
                "unit": "USD_per_share",
                "currency": "USD",
                "period": None,
                "basis": "non_gaap",
                "quote": "Non-GAAP EPS was $0.81",
            },  # not in the document -> memory/hallucination
        ],
    )
    r = p.extract_facts(DOC)
    assert r.status == "rejected_validation" and r.facts == () and "not found" in r.rejected[0]


# ---------------------------------------------------------------- Claude provider with a stub client
class StubMessages:
    def __init__(self, response: Any) -> None:
        self.response, self.calls = response, []

    def create(self, **kw: Any) -> Any:
        self.calls.append(kw)
        return self.response


def stub_client(response: Any) -> Any:
    return SimpleNamespace(beta=SimpleNamespace(messages=StubMessages(response)))


def response(text: str, stop: str = "end_turn", model: str = "claude-opus-5-5") -> Any:
    return SimpleNamespace(
        stop_reason=stop,
        model=model,
        stop_details=SimpleNamespace(category="cyber") if stop == "refusal" else None,
        content=[SimpleNamespace(type="text", text=text)],
        usage=SimpleNamespace(
            input_tokens=812, output_tokens=95, cache_read_input_tokens=0, cache_creation_input_tokens=0
        ),
    )


FACTS = {
    "facts": [
        {
            "metric": "revenue",
            "value": 35.1,
            "unit": "USD_billion",
            "currency": "USD",
            "period": "FY2027Q3",
            "basis": None,
            "quote": "Revenue for the quarter was $35.1 billion",
        }
    ]
}


def test_claude_request_shape_and_logging(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("LLM_MODEL", raising=False)
    client, log = stub_client(response(json.dumps(FACTS))), ListCallLogger()
    r = ClaudeProvider(logger=log, client=client).extract_facts(DOC, "docv_1", mode="replay")
    assert r.status == "succeeded" and r.facts[0].value == 35.1
    (kw,) = client.beta.messages.calls
    assert kw["model"] == "claude-opus-5-5"
    assert "tools" not in kw  # no tools => no web search, live or replay
    assert kw["output_config"] == {
        "effort": "high",
        "format": {"type": "json_schema", "schema": FACTS_SCHEMA},
    }
    assert kw["fallbacks"] == "default" and kw["betas"] == ["server-side-fallback-2026-07-01"]
    assert DOC in kw["messages"][0]["content"]
    (rec,) = log.records
    assert rec.mode == "replay" and rec.status == "succeeded" and rec.usage["input_tokens"] == 812
    assert rec.model == "claude-opus-5-5" and rec.output_hash and rec.request_params["tools"] == []


def test_claude_records_fallback_model() -> None:
    log = ListCallLogger()
    ClaudeProvider(
        logger=log, client=stub_client(response(json.dumps(FACTS), model="claude-opus-4-8"))
    ).extract_facts(DOC)
    assert log.records[0].model == "claude-opus-4-8"


def test_claude_refusal_and_bad_output() -> None:
    log = ListCallLogger()
    r = ClaudeProvider(logger=log, client=stub_client(response("", stop="refusal"))).extract_facts(DOC)
    assert r.status == "refused" and r.facts == () and log.records[0].error["message"] == "cyber"  # type: ignore[index]
    r2 = ClaudeProvider(logger=log, client=stub_client(response("{not json"))).extract_facts(DOC)
    assert r2.status == "failed" and log.records[1].error["code"] == "bad_json"  # type: ignore[index]
    r3 = ClaudeProvider(logger=log, client=stub_client(response("", stop="max_tokens"))).extract_facts(DOC)
    assert r3.status == "failed"


def test_claude_rejects_unverifiable_quotes() -> None:
    bad = {"facts": [{**FACTS["facts"][0], "quote": "Revenue was a record $40 billion"}]}
    r = ClaudeProvider(client=stub_client(response(json.dumps(bad)))).extract_facts(DOC)
    assert r.status == "rejected_validation" and r.facts == ()


def test_tools_must_stay_disabled(monkeypatch: pytest.MonkeyPatch) -> None:
    from sr.config import load

    cfg = load("llm")
    monkeypatch.setitem(cfg["rules"], "tools_allowed", ["web_search"])
    with pytest.raises(ValueError):
        ClaudeProvider(client=stub_client(response("{}")))
