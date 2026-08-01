"""Wayland connection primitives for the Phase 0 graphics spike."""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from pywayland.client.display import Display


class WaylandUnavailableError(RuntimeError):
    """Raised when the native Wayland client library cannot be loaded."""


def connect(display: str | None = None) -> Display:
    """Connect to a Wayland compositor.

    The returned object is PyWayland's ``Display``.  The import is deliberately
    lazy so image and shader code can be used without a Wayland session.
    """

    try:
        from pywayland.client.display import Display
    except ImportError as error:
        message = (
            "Wayland support is unavailable. Install libwayland-client and make "
            "its runtime library visible to the dynamic linker."
        )
        raise WaylandUnavailableError(message) from error

    connection = Display(display)
    try:
        connection.connect()
    except (OSError, ValueError) as error:
        message = (
            "Could not connect to a Wayland compositor. Check WAYLAND_DISPLAY "
            "and ensure a compositor session is running."
        )
        raise WaylandUnavailableError(message) from error
    return connection


__all__ = ["WaylandUnavailableError", "connect"]
