"""Typed failures for the PSR Ask plugin."""

from __future__ import annotations


class PSRAskError(Exception):
    """Base plugin error with a stable machine code."""

    def __init__(self, message: str, *, code: str, retryable: bool = False) -> None:
        super().__init__(message)
        self.message = message
        self.code = code
        self.retryable = retryable


class PSRAskConfigError(PSRAskError):
    """Invalid Runner binding configuration."""


class PSRAskIdentityError(PSRAskError):
    """Trusted platform identity could not be mapped to a backend ticket."""


class PSRAskTransportError(PSRAskError):
    """HTTP transport or protocol failure talking to /ask."""


class PSRAskBackendError(PSRAskError):
    """Backend returned an explicit non-success /ask result."""
