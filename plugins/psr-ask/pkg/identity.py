"""Resolve a backend /ask ticket from trusted Host identity + delivery config.

Tickets are never logged. Values are read only by environment variable name or
from an identity map that points to environment variable names.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping


from .errors import PSRAskConfigError, PSRAskIdentityError


@dataclass(frozen=True)
class ResolvedIdentity:
    """Backend-facing identity references without disclosing ticket bytes."""

    actor_id: str
    ticket_env: str
    correlation_id: str


def _nonempty(value: Any) -> str:
    text = str(value or "").strip()
    return text


def load_identity_map(path: str | None) -> dict[str, str]:
    """Load open_id -> ticket-env-name map. Values must be env names, not tickets."""
    if not path:
        return {}
    map_path = Path(path)
    if not map_path.is_file():
        raise PSRAskConfigError(
            f"identity map file not found: {map_path.name}",
            code="psr.identity_map_missing",
        )
    raw = json.loads(map_path.read_text(encoding="utf-8"))
    if not isinstance(raw, dict):
        raise PSRAskConfigError("identity map must be a JSON object", code="psr.identity_map_invalid")
    mapping: dict[str, str] = {}
    for key, value in raw.items():
        actor = _nonempty(key)
        env_name = _nonempty(value)
        if not actor or not env_name:
            raise PSRAskConfigError(
                "identity map entries must be non-empty strings",
                code="psr.identity_map_invalid",
            )
        if env_name.startswith("Bearer ") or len(env_name) > 128:
            raise PSRAskConfigError(
                "identity map values must be environment variable names, not tickets",
                code="psr.identity_map_invalid",
            )
        mapping[actor] = env_name
    return mapping


def resolve_ticket_env(
    *,
    actor_id: str | None,
    config: Mapping[str, Any],
    environ: Mapping[str, str] | None = None,
) -> ResolvedIdentity:
    """Choose which env var holds the user ticket for this trusted actor."""
    env = environ if environ is not None else os.environ
    actor = _nonempty(actor_id)
    if not actor:
        raise PSRAskIdentityError(
            "trusted Host actor identity is required",
            code="psr.identity_unavailable",
        )

    default_env = _nonempty(config.get("identity-ticket-env")) or "QUERY_BOT_PSR_USER_TICKET"
    map_file = _nonempty(config.get("identity-map-file"))
    mapping = load_identity_map(map_file) if map_file else {}

    if mapping:
        ticket_env = mapping.get(actor)
        if not ticket_env:
            raise PSRAskIdentityError(
                "no backend ticket mapping for this platform identity",
                code="psr.identity_unmapped",
            )
    else:
        # Fallback env-name hook only. Not B0 employee identity and not a
        # shared "one ticket for everyone" production path — see delivery
        # identity contract (per-request mapping). Temporary probe use only.
        ticket_env = default_env

    ticket = env.get(ticket_env)
    if ticket is None or not str(ticket).strip():
        raise PSRAskIdentityError(
            f"backend ticket environment variable is missing or empty: {ticket_env}",
            code="psr.identity_ticket_missing",
        )

    correlation = f"actor:{actor}"
    return ResolvedIdentity(actor_id=actor, ticket_env=ticket_env, correlation_id=correlation)


def read_ticket(resolved: ResolvedIdentity, environ: Mapping[str, str] | None = None) -> str:
    """Return the ticket string for HTTP use. Callers must not log the result."""
    env = environ if environ is not None else os.environ
    ticket = str(env.get(resolved.ticket_env, "")).strip()
    if not ticket:
        raise PSRAskIdentityError(
            f"backend ticket environment variable is missing or empty: {resolved.ticket_env}",
            code="psr.identity_ticket_missing",
        )
    if ticket.lower().startswith("bearer "):
        ticket = ticket[7:].strip()
    if not ticket:
        raise PSRAskIdentityError(
            "backend ticket is empty after normalization",
            code="psr.identity_ticket_missing",
        )
    return ticket
