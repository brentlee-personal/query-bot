"""Minimal HTTP client for PSR ToB POST /ask (protocol tob-go-v1)."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

import httpx

from .errors import PSRAskBackendError, PSRAskConfigError, PSRAskTransportError


SUPPORTED_PROTOCOL = "tob-go-v1"


@dataclass(frozen=True)
class AskSuccess:
    """Successful /ask payload normalized for presentation."""

    kind: str  # "knowledge" | "query"
    answer_text: str
    raw: Mapping[str, Any]
    request_id: str | None = None


@dataclass(frozen=True)
class AskFailure:
    ok: bool
    code: str
    http_status: int
    protocol_version: str | None = None


def normalize_base_url(base_url: str) -> str:
    url = (base_url or "").strip().rstrip("/")
    if not url:
        raise PSRAskConfigError("ask-base-url is required", code="psr.config_invalid")
    if url.endswith("/ask"):
        url = url[: -len("/ask")]
    return url


def build_ask_url(base_url: str) -> str:
    return normalize_base_url(base_url) + "/ask"


def _format_query_result(result: Mapping[str, Any]) -> str:
    columns = result.get("columns") or []
    rows = result.get("rows")
    if not isinstance(columns, list) or rows is None or not isinstance(rows, list):
        raise PSRAskTransportError(
            "query result missing columns/rows",
            code="psr.invalid_response",
        )
    if not columns:
        raise PSRAskTransportError("query result has no columns", code="psr.invalid_response")

    lines: list[str] = []
    header = " | ".join(str(c) for c in columns)
    lines.append(header)
    lines.append("-" * max(len(header), 3))
    if len(rows) == 0:
        lines.append("(无行)")
    else:
        for row in rows:
            if not isinstance(row, list):
                raise PSRAskTransportError("query row must be a list", code="psr.invalid_response")
            cells = ["" if cell is None else str(cell) for cell in row]
            lines.append(" | ".join(cells))
    query_sha = result.get("query_sha256")
    if isinstance(query_sha, str) and query_sha:
        lines.append(f"query_sha256: {query_sha[:12]}…")
    return "\n".join(lines)


def _format_knowledge(payload: Mapping[str, Any]) -> str:
    answer = payload.get("answer")
    if not isinstance(answer, str) or not answer.strip():
        raise PSRAskTransportError("knowledge answer missing", code="psr.invalid_response")
    lines = [answer.strip()]
    citations = payload.get("citations")
    if isinstance(citations, list) and citations:
        lines.append("")
        lines.append("依据：")
        for index, citation in enumerate(citations, start=1):
            if not isinstance(citation, Mapping):
                continue
            chunk = citation.get("chunk_id") or citation.get("ChunkID") or ""
            document = citation.get("document_id") or citation.get("DocumentID") or ""
            dataset = citation.get("dataset_id") or citation.get("DatasetID") or ""
            parts = [p for p in (f"dataset={dataset}" if dataset else "", f"document={document}" if document else "", f"chunk={chunk}" if chunk else "") if p]
            if parts:
                lines.append(f"{index}. " + ", ".join(parts))
    return "\n".join(lines)


def parse_ask_response(http_status: int, body: bytes) -> AskSuccess | AskFailure:
    try:
        payload = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise PSRAskTransportError("response is not JSON", code="psr.invalid_response") from exc
    if not isinstance(payload, dict):
        raise PSRAskTransportError("response JSON must be an object", code="psr.invalid_response")

    protocol = payload.get("protocol_version")
    ok = payload.get("ok")
    if ok is False:
        code = str(payload.get("code") or "UNKNOWN_FAILURE")
        return AskFailure(
            ok=False,
            code=code,
            http_status=http_status,
            protocol_version=str(protocol) if protocol is not None else None,
        )
    if ok is not True:
        raise PSRAskTransportError("response missing ok=true", code="psr.invalid_response")
    if protocol != SUPPORTED_PROTOCOL:
        raise PSRAskTransportError(
            f"unsupported protocol_version: {protocol!r}",
            code="psr.unsupported_protocol",
        )

    if "answer" in payload:
        text = _format_knowledge(payload)
        return AskSuccess(kind="knowledge", answer_text=text, raw=payload)
    if "result" in payload and isinstance(payload.get("result"), dict):
        text = _format_query_result(payload["result"])
        return AskSuccess(kind="query", answer_text=text, raw=payload)
    raise PSRAskTransportError(
        "success response missing answer or result",
        code="psr.invalid_response",
    )


async def post_ask(
    *,
    base_url: str,
    question: str,
    ticket: str,
    timeout_seconds: float = 120.0,
    client: httpx.AsyncClient | None = None,
    correlation_id: str | None = None,
) -> AskSuccess:
    """POST /ask. Never logs the ticket. Raises typed errors on failure."""
    q = (question or "").strip()
    if not q:
        raise PSRAskConfigError("question is empty", code="psr.empty_question")
    if len(q) > 8192:
        raise PSRAskConfigError("question exceeds backend limit", code="psr.question_too_long")

    url = build_ask_url(base_url)
    headers = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "Authorization": f"Bearer {ticket}",
        "Cache-Control": "no-store",
    }
    if correlation_id:
        headers["X-Request-ID"] = correlation_id

    owns_client = client is None
    http = client or httpx.AsyncClient(timeout=timeout_seconds, follow_redirects=False)
    try:
        response = await http.post(url, headers=headers, json={"question": q})
    except httpx.TimeoutException as exc:
        raise PSRAskTransportError("ask request timed out", code="psr.timeout", retryable=True) from exc
    except httpx.HTTPError as exc:
        raise PSRAskTransportError("ask transport failed", code="psr.transport_error", retryable=True) from exc
    finally:
        if owns_client:
            await http.aclose()

    parsed = parse_ask_response(response.status_code, response.content)
    if isinstance(parsed, AskFailure):
        retryable = parsed.code in {"REQUEST_TIMEOUT", "QUESTION_UNAVAILABLE", "READONLY_QUERY_UNAVAILABLE"}
        raise PSRAskBackendError(
            f"backend refused ask: {parsed.code}",
            code=f"psr.backend.{parsed.code}",
            retryable=retryable,
        )
    if not parsed.answer_text.strip():
        raise PSRAskTransportError("backend returned an empty business answer", code="psr.empty_answer")
    return parsed
