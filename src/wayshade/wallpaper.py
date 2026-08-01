"""Layer-shell wallpaper surface for the Phase 0 feasibility spike."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from ._protocol.wlr_layer_shell_unstable_v1.zwlr_layer_shell_v1 import (
    ZwlrLayerShellV1,
)
from ._protocol.wlr_layer_shell_unstable_v1.zwlr_layer_surface_v1 import (
    ZwlrLayerSurfaceV1,
)
from .wayland_session import WaylandGlobals, discover_globals


class WallpaperSurfaceError(RuntimeError):
    """Raised when a wallpaper surface cannot be configured."""


@dataclass
class WallpaperSurface:
    """A configured, fullscreen background layer surface.

    The surface has no buffer attached yet. EGL/Wayland buffer creation is the
    next Phase 0 step.
    """

    globals: WaylandGlobals
    surface: Any
    layer_surface: Any
    width: int
    height: int
    closed: bool = False

    def close(self) -> None:
        """Destroy the layer surface and close its Wayland connection."""

        if not self.closed:
            self.layer_surface.destroy()
            self.surface.destroy()
            self.globals.close()
            self.closed = True


def create_wallpaper(
    display_name: str | None = None,
    namespace: str = "wayshade",
) -> WallpaperSurface:
    """Create and configure a fullscreen background surface.

    The first implementation targets the first output advertised by the
    compositor. Passing ``None`` to layer-shell lets the compositor select that
    output according to its normal policy.
    """

    globals = discover_globals(display_name)
    try:
        surface = globals.compositor.create_surface()
        layer_surface = globals.layer_shell.get_layer_surface(
            surface,
            globals.output,
            ZwlrLayerShellV1.layer.background,
            namespace,
        )

        state: dict[str, int | bool] = {"width": 0, "height": 0, "configured": False}

        def on_configure(
            _layer: ZwlrLayerSurfaceV1, serial: int, width: int, height: int
        ) -> None:
            layer_surface.ack_configure(serial)
            state.update(width=width, height=height, configured=True)

        def on_closed(_layer: ZwlrLayerSurfaceV1) -> None:
            state["closed"] = True

        layer_surface.dispatcher["configure"] = on_configure
        layer_surface.dispatcher["closed"] = on_closed
        layer_surface.set_size(0, 0)
        layer_surface.set_anchor(
            int(
                ZwlrLayerSurfaceV1.anchor.top
                | ZwlrLayerSurfaceV1.anchor.bottom
                | ZwlrLayerSurfaceV1.anchor.left
                | ZwlrLayerSurfaceV1.anchor.right
            )
        )
        layer_surface.set_exclusive_zone(-1)
        layer_surface.set_keyboard_interactivity(
            ZwlrLayerSurfaceV1.keyboard_interactivity.none
        )
        surface.commit()
        globals.display.roundtrip()

        if not state.get("configured"):
            raise WallpaperSurfaceError(
                "Compositor did not configure the wallpaper surface"
            )
        if state.get("closed"):
            raise WallpaperSurfaceError("Compositor closed the wallpaper surface")

        return WallpaperSurface(
            globals,
            surface,
            layer_surface,
            int(state["width"]),
            int(state["height"]),
        )
    except Exception:
        globals.close()
        raise


__all__ = ["WallpaperSurface", "WallpaperSurfaceError", "create_wallpaper"]
