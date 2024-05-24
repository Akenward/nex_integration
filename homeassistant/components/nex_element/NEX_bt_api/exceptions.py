"""Exceptions for NEX_bt_api."""

from bleak import BleakError


class BleakTimeout(TimeoutError):
    """Timeout exception for Bleak connection."""


class BleakConnectionFailure(BleakError):
    """Failure of Bleak connection attempt."""


class ApiError(Exception):
    """Failure of API to return data."""
