"""The explicit single-output rendering session."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .image import Image
from .shader import Shader
from .wallpaper import WallpaperSurface, create_wallpaper


class RendererError(RuntimeError):
    """Raised when a renderer operation cannot be completed."""


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

    def __init__(self, wallpaper: WallpaperSurface) -> None:
        self.wallpaper = wallpaper
        self.target = Target(wallpaper)
        self._images: list[Image] = []
        self.closed = False

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

    def wait_for_frame(self) -> None:
        if self.closed:
            raise RendererError("Renderer is closed")
        self.wallpaper.wait_for_frame()

    def close(self) -> None:
        if not self.closed:
            self.wallpaper.close()
            self._images.clear()
            self.closed = True


def create(*, output: int | None = None, display_name: str | None = None) -> Renderer:
    """Create a renderer for the first output or numeric ``output`` index."""
    return Renderer(create_wallpaper(display_name=display_name, output=output))


__all__ = ["Renderer", "RendererError", "Target", "create"]
