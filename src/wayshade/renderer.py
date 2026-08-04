"""The explicit single-output rendering session."""

from __future__ import annotations

import atexit
import signal
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType
from typing import Any, Self

from .image import Image
from .shader import Shader
from .wallpaper import WallpaperSurface, create_wallpaper


class RendererError(RuntimeError):
    """Raised when a renderer operation cannot be completed."""


@dataclass(frozen=True)
class Frame:
    """Timing and output information for one convenience-loop update."""

    time: float
    delta_time: float
    width: int
    height: int
    output: int | None = None

    def uniforms(self) -> dict[str, float | int]:
        """Return frame values in the form accepted by ``Shader.set``.

        ``output`` is omitted when no numeric output was selected, since GLSL
        uniforms cannot represent ``None``.
        """
        values: dict[str, float | int] = {
            "time": self.time,
            "delta_time": self.delta_time,
            "width": self.width,
            "height": self.height,
        }
        if self.output is not None:
            values["output"] = self.output
        return values


@dataclass(frozen=True)
class Target:
    """A writable renderer destination."""

    resource: WallpaperSurface | Image

    @property
    def width(self) -> int:
        return self.resource.width

    @property
    def height(self) -> int:
        return self.resource.height


class Renderer:
    """Own one Wayland wallpaper target and its graphics session."""

    def __init__(
        self, wallpaper: WallpaperSurface, *, output: int | None = None
    ) -> None:
        self.wallpaper = wallpaper
        self.output = output
        self.target = Target(wallpaper)
        self._images: list[Image] = []
        self.closed = False
        self._exit_cleanup = self.close
        atexit.register(self._exit_cleanup)

    def load_shader(self, source: str) -> Shader:
        """Create a fragment shader from GLSL source."""
        return Shader(source)

    def load_shader_file(self, path: str | Path) -> Shader:
        """Create a fragment shader from a UTF-8 file."""
        return Shader.from_file(path)

    def load_image(self, path: str | Path) -> Image:
        """Load a PNG, JPEG, WebP, or other Pillow-supported image as RGBA8."""
        image = Image.from_file(path)
        self._images.append(image)
        return image

    def draw(
        self,
        shader: Shader | Image,
        *,
        to: Target | WallpaperSurface | Image | None = None,
        textures: dict[str, Image] | None = None,
    ) -> Image | None:
        """Draw a shader or image, producing an intermediate image by default."""
        if self.closed:
            raise RendererError("Renderer is closed")
        if isinstance(shader, Image):
            if textures:
                raise RendererError("Image draws do not accept texture inputs")
            source = shader
            shader = self.load_shader("""
                #version 120
                uniform sampler2D source;
                varying vec2 uv;
                void main() { gl_FragColor = texture2D(source, uv); }
            """)
            textures = {"source": source}
        destination: WallpaperSurface | Image
        if to is None:
            destination = Image.empty(self.wallpaper.width, self.wallpaper.height)
            self._images.append(destination)
        elif isinstance(to, Target):
            destination = to.resource
        else:
            destination = to
        if destination is not self.wallpaper and not isinstance(destination, Image):
            raise RendererError("Invalid renderer target")
        if isinstance(destination, Image) and destination is shader:
            raise RendererError("An image cannot be drawn to itself")
        if textures and any(
            not isinstance(image, Image) for image in textures.values()
        ):
            raise RendererError("Textures must be Image objects")
        if isinstance(destination, Image):
            if destination not in self._images:
                self._images.append(destination)
            presenter = self._presenter()
            presenter.ensure_image(destination)
        else:
            presenter = self._presenter()
        if isinstance(destination, Image):
            presenter.render_shader(shader, textures or {}, destination, swap=False)
            return destination
        if destination.frame_pending:
            raise RendererError(
                "A frame is already pending; call wait_for_frame() first"
            )
        destination._request_frame()
        try:
            presenter.render_shader(shader, textures or {}, destination, swap=True)
        except Exception:
            if destination.frame_callback is not None:
                destination.frame_callback.destroy()
            destination.frame_callback = None
            destination.frame_pending = False
            raise

    def _presenter(self) -> Any:
        if self.wallpaper.presenter is None:
            from .egl import EglPresenter

            self.wallpaper.presenter = EglPresenter(
                self.wallpaper.globals.display,
                self.wallpaper.surface,
                self.wallpaper.width,
                self.wallpaper.height,
            )
        return self.wallpaper.presenter

    def __enter__(self) -> Self:
        return self

    def __exit__(
        self,
        _type: type[BaseException] | None,
        _value: BaseException | None,
        _traceback: TracebackType | None,
    ) -> None:
        self.close()

    def wait_for_frame(self) -> None:
        if self.closed:
            raise RendererError("Renderer is closed")
        self.wallpaper.wait_for_frame()

    def run(self, update: Callable[[Frame], object]) -> None:
        """Call ``update`` once per compositor-paced frame.

        The callback owns rendering and may return ``False`` to stop the loop.
        Any other return value continues it. The first update runs immediately;
        later updates wait for the previous draw's Wayland frame callback.
        """
        if self.closed:
            raise RendererError("Renderer is closed")
        if not callable(update):
            raise TypeError("update must be callable")
        started = time.monotonic()
        previous = started
        interrupted = False
        previous_handler = None

        def on_interrupt(_signum: int, _frame: object) -> None:
            nonlocal interrupted
            interrupted = True

        # Raising KeyboardInterrupt from inside PyWayland's CFFI dispatcher
        # callback is ignored by cffi. Record SIGINT instead and let the native
        # dispatch return so the loop can cleanly unwind.
        if threading.current_thread() is threading.main_thread():
            previous_handler = signal.signal(signal.SIGINT, on_interrupt)
        try:
            while True:
                if interrupted:
                    return
                now = time.monotonic()
                frame = Frame(
                    time=now - started,
                    delta_time=now - previous,
                    width=self.wallpaper.width,
                    height=self.wallpaper.height,
                    output=self.output,
                )
                previous = now
                if update(frame) is False or interrupted:
                    return
                if self.closed:
                    return
                if self.wallpaper.frame_pending:
                    try:
                        self.wait_for_frame()
                    except RuntimeError:
                        if interrupted:
                            return
                        raise
        except KeyboardInterrupt:
            return
        finally:
            if previous_handler is not None:
                signal.signal(signal.SIGINT, previous_handler)

    def close(self) -> None:
        atexit.unregister(self._exit_cleanup)
        if not self.closed:
            self.wallpaper.close()
            self._images.clear()
            self.closed = True


def create(*, output: int | None = None, display_name: str | None = None) -> Renderer:
    """Create a renderer for the first output or numeric ``output`` index."""
    return Renderer(
        create_wallpaper(display_name=display_name, output=output), output=output
    )


__all__ = ["Frame", "Renderer", "RendererError", "Target", "create"]
