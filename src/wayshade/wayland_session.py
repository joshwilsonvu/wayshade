"""Wayland global discovery used by the Phase 0 compositor spike."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from .wayland import WaylandUnavailableError, connect


class MissingWaylandGlobalError(RuntimeError):
    """Raised when the compositor lacks a required protocol global."""


@dataclass
class WaylandGlobals:
    """The protocol objects needed to create a wallpaper surface."""

    display: Any
    compositor: Any
    layer_shell: Any
    output: Any | None

    def close(self) -> None:
        """Release protocol objects and close the compositor connection."""

        self.display.disconnect()


def discover_globals(display_name: str | None = None) -> WaylandGlobals:
    """Connect to Wayland and bind the globals required by Wayshade.

    The first output is intentionally used as the default. Output selection by
    index will be added when the surface/session object is implemented.
    """

    try:
        from pywayland.protocol.wayland.wl_compositor import WlCompositor
        from pywayland.protocol.wayland.wl_output import WlOutput

        from ._protocol.wlr_layer_shell_unstable_v1.zwlr_layer_shell_v1 import (
            ZwlrLayerShellV1,
        )
    except ImportError as error:
        raise WaylandUnavailableError(
            "Wayland protocol bindings could not be imported."
        ) from error

    display: Any = connect(display_name)
    registry = display.get_registry()
    globals_by_name: dict[str, tuple[int, Any]] = {}

    def on_global(_registry: Any, name: int, interface: str, version: int) -> None:
        globals_by_name[interface] = (name, version)

    registry.dispatcher["global"] = on_global
    try:
        display.roundtrip()

        required = ("wl_compositor", "zwlr_layer_shell_v1")
        missing = [name for name in required if name not in globals_by_name]
        if missing:
            names = ", ".join(missing)
            raise MissingWaylandGlobalError(
                f"The compositor does not advertise required Wayland globals: {names}"
            )

        compositor_name, compositor_version = globals_by_name["wl_compositor"]
        layer_name, layer_version = globals_by_name["zwlr_layer_shell_v1"]
        compositor = registry.bind(
            compositor_name, WlCompositor, min(compositor_version, 1)
        )
        layer_shell = registry.bind(layer_name, ZwlrLayerShellV1, min(layer_version, 4))

        output = None
        if "wl_output" in globals_by_name:
            output_name, output_version = globals_by_name["wl_output"]
            output = registry.bind(output_name, WlOutput, min(output_version, 1))

        return WaylandGlobals(display, compositor, layer_shell, output)
    except Exception:
        display.disconnect()
        raise


__all__ = [
    "MissingWaylandGlobalError",
    "WaylandGlobals",
    "discover_globals",
]
