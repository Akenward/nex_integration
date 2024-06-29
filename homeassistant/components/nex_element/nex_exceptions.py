"""Exceptions for NEX integration."""


class ServiceNotAvailableError(Exception):
    """Service restricted."""


class CancelledError(Exception):
    """Operation cancelled."""
