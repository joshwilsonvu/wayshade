from typing import Any, cast

import pytest

from wayshade import WallpaperSurface, WallpaperSurfaceError, WaylandUnavailableError
from wayshade._protocol.wlr_layer_shell_unstable_v1.zwlr_layer_shell_v1 import (
    ZwlrLayerShellV1,
)
from wayshade._protocol.wlr_layer_shell_unstable_v1.zwlr_layer_surface_v1 import (
    ZwlrLayerSurfaceV1,
)


def test_layer_shell_bindings_are_packaged() -> None:
    assert ZwlrLayerShellV1.name == "zwlr_layer_shell_v1"
    assert ZwlrLayerSurfaceV1.name == "zwlr_layer_surface_v1"


def test_error_is_public() -> None:
    assert issubclass(WaylandUnavailableError, RuntimeError)


def test_wallpaper_waits_for_frame_callback() -> None:
    class Callback:
        def __init__(self) -> None:
            self.dispatcher: dict[str, object] = {}
            self.destroyed = False

        def destroy(self) -> None:
            self.destroyed = True

        def complete(self) -> None:
            handler = self.dispatcher["done"]
            assert callable(handler)
            handler(self, 0)

    class Display:
        def __init__(self, callback: Callback) -> None:
            self.callback = callback

        def dispatch(self, *, block: bool) -> int:
            assert block
            self.callback.complete()
            return 0

    class Surface:
        def __init__(self) -> None:
            self.callback = Callback()

        def frame(self) -> Callback:
            return self.callback

        def destroy(self) -> None:
            pass

    class LayerSurface:
        def destroy(self) -> None:
            pass

    class Globals:
        def __init__(self, display: Display) -> None:
            self.display = display

        def close(self) -> None:
            pass

    class Presenter:
        def __init__(self) -> None:
            self.colors: list[tuple[float, float, float, float]] = []

        def clear_and_swap(self, color: tuple[float, float, float, float]) -> None:
            self.colors.append(color)

        def close(self) -> None:
            pass

    surface = Surface()
    globals = Globals(Display(surface.callback))
    wallpaper = WallpaperSurface(
        cast(Any, globals),
        surface,
        LayerSurface(),
        100,
        100,
        presenter=cast(Any, Presenter()),
    )

    wallpaper.present_solid()
    assert wallpaper.frame_pending
    with pytest.raises(WallpaperSurfaceError, match="already pending"):
        wallpaper.present_solid()

    wallpaper.wait_for_frame()
    assert not wallpaper.frame_pending
    assert surface.callback.destroyed
