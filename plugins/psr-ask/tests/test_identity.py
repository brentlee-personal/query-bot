"""Identity resolution tests — env names and presence only, never ticket values."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from pkg.errors import PSRAskIdentityError
from pkg.identity import read_ticket, resolve_ticket_env


def test_default_ticket_env(tmp_path: Path) -> None:
    env = {"QUERY_BOT_PSR_USER_TICKET": "synthetic-ticket-value"}
    resolved = resolve_ticket_env(
        actor_id="ou_synthetic_authorized",
        config={},
        environ=env,
    )
    assert resolved.ticket_env == "QUERY_BOT_PSR_USER_TICKET"
    assert read_ticket(resolved, environ=env) == "synthetic-ticket-value"


def test_identity_map_uses_env_names(tmp_path: Path) -> None:
    map_path = tmp_path / "map.json"
    map_path.write_text(
        json.dumps({"ou_synthetic_authorized": "TICKET_FOR_A", "ou_other": "TICKET_FOR_B"}),
        encoding="utf-8",
    )
    env = {"TICKET_FOR_A": "aaa", "TICKET_FOR_B": "bbb"}
    resolved = resolve_ticket_env(
        actor_id="ou_synthetic_authorized",
        config={"identity-map-file": str(map_path)},
        environ=env,
    )
    assert resolved.ticket_env == "TICKET_FOR_A"


def test_unmapped_actor_is_denied(tmp_path: Path) -> None:
    map_path = tmp_path / "map.json"
    map_path.write_text(json.dumps({"ou_allowed": "TICKET_FOR_A"}), encoding="utf-8")
    with pytest.raises(PSRAskIdentityError) as exc:
        resolve_ticket_env(
            actor_id="ou_unauthorized",
            config={"identity-map-file": str(map_path)},
            environ={"TICKET_FOR_A": "aaa"},
        )
    assert exc.value.code == "psr.identity_unmapped"


def test_missing_ticket_env_fails_closed() -> None:
    with pytest.raises(PSRAskIdentityError) as exc:
        resolve_ticket_env(
            actor_id="ou_synthetic",
            config={},
            environ={},
        )
    assert exc.value.code == "psr.identity_ticket_missing"
