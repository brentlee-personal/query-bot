"""Unit tests for /ask client parsing with synthetic payloads only."""

from __future__ import annotations

import json
from pathlib import Path

import httpx
import pytest

from pkg.ask_client import AskFailure, AskSuccess, parse_ask_response, post_ask
from pkg.errors import PSRAskBackendError


EXAMPLES = Path(__file__).resolve().parents[1] / "examples"


def test_parse_query_success() -> None:
    body = (EXAMPLES / "synthetic_ask_success_query.json").read_bytes()
    parsed = parse_ask_response(200, body)
    assert isinstance(parsed, AskSuccess)
    assert parsed.kind == "query"
    assert parsed.request_id == "req-synthetic-query-001"
    assert "synthetic_sales" in parsed.answer_text
    assert "42" in parsed.answer_text
    assert "件" in parsed.answer_text


def test_parse_knowledge_success() -> None:
    body = (EXAMPLES / "synthetic_ask_success_knowledge.json").read_bytes()
    parsed = parse_ask_response(200, body)
    assert isinstance(parsed, AskSuccess)
    assert parsed.kind == "knowledge"
    assert parsed.request_id == "req-synthetic-knowledge-001"
    assert "合成知识答案" in parsed.answer_text
    assert "chunk-synthetic" in parsed.answer_text


def test_parse_auth_required() -> None:
    body = (EXAMPLES / "synthetic_ask_denied.json").read_bytes()
    parsed = parse_ask_response(401, body)
    assert isinstance(parsed, AskFailure)
    assert parsed.code == "AUTHENTICATION_REQUIRED"


@pytest.mark.asyncio
async def test_post_ask_unauthorized_counter_example() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path.endswith("/ask")
        assert request.headers.get("authorization") == "Bearer definitely-invalid"
        return httpx.Response(
            401,
            json={"ok": False, "protocol_version": "tob-go-v1", "code": "AUTHENTICATION_DENIED"},
        )

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        with pytest.raises(PSRAskBackendError) as exc:
            await post_ask(
                base_url="http://psr.example",
                question="synthetic question",
                ticket="definitely-invalid",
                client=client,
            )
    assert exc.value.code == "psr.backend.AUTHENTICATION_DENIED"


@pytest.mark.asyncio
async def test_post_ask_query_success_roundtrip() -> None:
    payload = json.loads((EXAMPLES / "synthetic_ask_success_query.json").read_text(encoding="utf-8"))

    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode("utf-8"))
        assert body == {"question": "合成问数题"}
        assert request.headers.get("content-type", "").startswith("application/json")
        return httpx.Response(200, json=payload)

    transport = httpx.MockTransport(handler)
    async with httpx.AsyncClient(transport=transport) as client:
        result = await post_ask(
            base_url="http://psr.example/",
            question="合成问数题",
            ticket="synthetic-ticket",
            client=client,
        )
    assert result.kind == "query"
    assert result.request_id == "req-synthetic-query-001"
    assert "42" in result.answer_text
