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
from .egl import EglPresenter
from .wayland_session import WaylandGlobals, discover_globals


class WallpaperSurfaceError(RuntimeError):
    """Raised when a wallpaper surface cannot be configured."""


@dataclass
class WallpaperSurface:
    """A configured, fullscreen background layer surface."""

    globals: WaylandGlobals
    surface: Any
    layer_surface: Any
    width: int
    height: int
    presenter: EglPresenter | None = None
    frame_callback: Any = None
    frame_pending: bool = False
    closed: bool = False

    def _request_frame(self) -> None:
        callback = self.surface.frame()

        def on_done(_callback: Any, _callback_data: int) -> None:
            self.frame_pending = False
            self.frame_callback = None
            callback.destroy()

        callback.dispatcher["done"] = on_done
        self.frame_callback = callback
        self.frame_pending = True

    def present_solid(
        self, color: tuple[float, float, float, float] = (0.08, 0.08, 0.12, 1.0)
    ) -> None:
        """Create EGL, then present one paced solid-color frame.

        Call :meth:`wait_for_frame` before presenting the next frame. The first
        frame can be presented immediately; subsequent frames are rejected
        while the compositor's callback is outstanding.
        """

        if self.closed:
            raise WallpaperSurfaceError("Wallpaper surface is closed")
        if self.frame_pending:
            raise WallpaperSurfaceError(
                "A frame is already pending; call wait_for_frame() first"
            )
        if self.presenter is None:
            self.presenter = EglPresenter(
                self.globals.display, self.surface, self.width, self.height
            )
        self._request_frame()
        try:
            self.presenter.clear_and_swap(color)
        except Exception:
            self.frame_callback.destroy()
            self.frame_callback = None
            self.frame_pending = False
            raise

    def offscreen_test(self) -> None:
        """Run the backend's offscreen texture sampling feasibility probe."""

        if self.closed:
            raise WallpaperSurfaceError("Wallpaper surface is closed")
        if self.frame_pending:
            raise WallpaperSurfaceError(
                "A frame is already pending; call wait_for_frame() first"
            )
        if self.presenter is None:
            self.presenter = EglPresenter(
                self.globals.display, self.surface, self.width, self.height
            )
        self._request_frame()
        try:
            self.presenter.offscreen_test_and_swap()
        except Exception:
            self.frame_callback.destroy()
            self.frame_callback = None
            self.frame_pending = False
            raise

    def wait_for_frame(self) -> None:
        """Block until the compositor permits the next frame."""

        while self.frame_pending:
            if self.globals.display.dispatch(block=True) < 0:
                self.frame_pending = False
                raise WallpaperSurfaceError(
                    "Wayland dispatch failed while waiting for a frame"
                )

    def close(self) -> None:
        """Release EGL, then destroy the layer surface and Wayland connection."""

        if not self.closed:
            if self.frame_callback is not None:
                self.frame_callback.destroy()
                self.frame_callback = None
                self.frame_pending = False
            if self.presenter is not None:
                self.presenter.close()
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
            assert layer_surface is not None
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
        layer_surface = locals().get("layer_surface")
        surface = locals().get("surface")
        if layer_surface is not None:
            layer_surface.destroy()
        if surface is not None:
            surface.destroy()
        globals.close()
        raise


__all__ = ["WallpaperSurface", "WallpaperSurfaceError", "create_wallpaper"]
