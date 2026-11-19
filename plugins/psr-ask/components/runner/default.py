"""LangBot Runner that forwards one user question to PSR ToB /ask."""

from __future__ import annotations

import logging
import os
import typing

from langbot_plugin.api.definition.components.runner.runner import Runner
from langbot_plugin.api.entities.builtin.provider.message import Message
from langbot_plugin.api.entities.builtin.runner import RunnerContext, RunnerResult

from pkg.ask_client import post_ask
from pkg.errors import PSRAskError
from pkg.identity import read_ticket, resolve_ticket_env

logger = logging.getLogger(__name__)


class DefaultRunner(Runner):
    """Agent Runner for PSR ToB POST /ask (protocol tob-go-v1)."""

    def _base_url(self, ctx: RunnerContext) -> str:
        env_url = os.environ.get("QUERY_BOT_PSR_ASK_BASE_URL", "").strip()
        config_url = str((ctx.config or {}).get("ask-base-url") or "").strip()
        return env_url or config_url

    def _timeout(self, ctx: RunnerContext) -> float:
        raw = (ctx.config or {}).get("timeout-seconds", 120)
        try:
            value = float(raw)
        except (TypeError, ValueError):
            value = 120.0
        return max(1.0, min(value, 120.0))

    def _actor_id(self, ctx: RunnerContext) -> str | None:
        actor = ctx.actor
        if actor is None:
            return None
        return getattr(actor, "actor_id", None)

    async def run(self, ctx: RunnerContext) -> typing.AsyncGenerator[RunnerResult, None]:
        question = ctx.input.to_text().strip() if ctx.input is not None else ""
        if not question:
            yield RunnerResult.run_failed(
                ctx.run_id,
                error="empty user question",
                code="psr.empty_question",
            )
            return

        try:
            resolved = resolve_ticket_env(
                actor_id=self._actor_id(ctx),
                config=ctx.config or {},
            )
            ticket = read_ticket(resolved)
            base_url = self._base_url(ctx)
            result = await post_ask(
                base_url=base_url,
                question=question,
                ticket=ticket,
                timeout_seconds=self._timeout(ctx),
                correlation_id=f"{ctx.run_id}:{resolved.correlation_id}",
            )
        except PSRAskError as exc:
            logger.info(
                "psr ask failed code=%s retryable=%s run_id=%s",
                exc.code,
                exc.retryable,
                ctx.run_id,
            )
            # Surface backend meaning; do not invent a success answer.
            yield RunnerResult.message_completed(
                ctx.run_id,
                Message(
                    role="assistant",
                    content=(
                        f"查询未能完成（{exc.code}）。\n"
                        f"{exc.message}\n"
                        "如持续失败，请回复「这条不对」，并保留本条消息。"
                    ),
                ),
            )
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=exc.message,
                code=exc.code,
                retryable=exc.retryable,
            )
            return
        except Exception as exc:  # noqa: BLE001 — terminal failure for the host
            logger.exception("psr ask unexpected error run_id=%s", ctx.run_id)
            yield RunnerResult.run_failed(
                ctx.run_id,
                error=f"unexpected runner error: {type(exc).__name__}",
                code="psr.unexpected_error",
            )
            return

        # Present backend business content only; no model rewrite.
        # Preserve backend request_id in host-visible metadata when present.
        prefix = "查询结果：\n" if result.kind == "query" else ""
        body = prefix + result.answer_text
        metadata: dict[str, typing.Any] = {}
        if result.request_id:
            metadata["psr_request_id"] = result.request_id
        completed = RunnerResult.message_completed(
            ctx.run_id,
            Message(role="assistant", content=body),
        )
        if metadata:
            completed = completed.model_copy(update={"metadata": metadata})
        yield completed
        yield RunnerResult.run_completed(ctx.run_id)
