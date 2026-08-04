from typing import Any, cast

import pytest

from wayshade import (
    Image,
    ImageError,
    Shader,
    WallpaperSurface,
    WallpaperSurfaceError,
    WaylandUnavailableError,
)
from wayshade._protocol.wlr_layer_shell_unstable_v1.zwlr_layer_shell_v1 import (
    ZwlrLayerShellV1,
)
from wayshade._protocol.wlr_layer_shell_unstable_v1.zwlr_layer_surface_v1 import (
    ZwlrLayerSurfaceV1,
)
from wayshade.egl import EglPresenter


def test_program_cache_compiles_each_source_once() -> None:
    class FakeGl:
        GL_VERTEX_SHADER = 1
        GL_FRAGMENT_SHADER = 2
        GL_COMPILE_STATUS = 3
        GL_LINK_STATUS = 4

        def __init__(self) -> None:
            self.created_shaders = 0
            self.created_programs = 0
            self.deleted_shaders = 0

        def glCreateShader(self, _shader_type: int) -> int:
            self.created_shaders += 1
            return self.created_shaders

        def glShaderSource(self, _shader: int, _source: str) -> None:
            pass

        def glCompileShader(self, _shader: int) -> None:
            pass

        def glGetShaderiv(self, _shader: int, _parameter: int) -> bool:
            return True

        def glCreateProgram(self) -> int:
            self.created_programs += 1
            return self.created_programs

        def glAttachShader(self, _program: int, _shader: int) -> None:
            pass

        def glBindAttribLocation(self, _program: int, _index: int, _name: str) -> None:
            pass

        def glLinkProgram(self, _program: int) -> None:
            pass

        def glGetProgramiv(self, _program: int, _parameter: int) -> bool:
            return True

        def glDeleteShader(self, _shader: int) -> None:
            self.deleted_shaders += 1

        def glDeleteProgram(self, _program: int) -> None:
            pass

    presenter = EglPresenter.__new__(EglPresenter)
    presenter._gl = FakeGl()
    presenter._programs = {}

    first = presenter._program_for("void main() {}")
    second = presenter._program_for("void main() {}")

    assert first == second
    assert presenter._gl.created_programs == 1
    assert presenter._gl.created_shaders == 2
    assert presenter._gl.deleted_shaders == 2


def test_layer_shell_bindings_are_packaged() -> None:
    assert ZwlrLayerShellV1.name == "zwlr_layer_shell_v1"
    assert ZwlrLayerSurfaceV1.name == "zwlr_layer_surface_v1"


def test_error_is_public() -> None:
    assert issubclass(WaylandUnavailableError, RuntimeError)


def test_image_loads_as_rgba8(tmp_path: Any) -> None:
    from PIL import Image as PillowImage

    path = tmp_path / "sample.png"
    PillowImage.new("RGB", (2, 3), (10, 20, 30)).save(path)
    image = Image.from_file(path)
    assert (image.width, image.height) == (2, 3)
    assert len(image.pixels or b"") == 2 * 3 * 4


def test_image_missing_file_is_actionable() -> None:
    with pytest.raises(ImageError, match="Could not load image"):
        Image.from_file("does-not-exist.png")


def test_shader_uniform_state_is_persistent() -> None:
    shader = Shader("void main() {}")
    assert shader.set("amount", 1.5).set({"resolution": (2.0, 3.0)}) is shader
    assert shader.uniforms == {"amount": 1.5, "resolution": (2.0, 3.0)}


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
