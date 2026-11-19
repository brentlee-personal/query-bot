"""PSR Ask plugin entry point."""

from __future__ import annotations

from langbot_plugin.api.definition.plugin import BasePlugin


class PSRAskPlugin(BasePlugin):
    """Installable LangBot plugin that exposes the PSR Ask Runner."""

    async def initialize(self) -> None:
        return None
