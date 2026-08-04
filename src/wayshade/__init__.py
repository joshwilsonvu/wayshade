"""Wayshade: a Python-controlled shader wallpaper renderer for Wayland."""

from .egl import EglPresentationError, EglUnavailableError
from .image import Image, ImageError
from .renderer import Frame, Renderer, RendererError, Target, create
from .shader import Shader, ShaderError
from .wallpaper import WallpaperSurface, WallpaperSurfaceError, create_wallpaper
from .wayland import WaylandUnavailableError, connect
from .wayland_session import (
    MissingWaylandGlobalError,
    WaylandGlobals,
    discover_globals,
)

__all__ = [
    "EglPresentationError",
    "EglUnavailableError",
    "Frame",
    "Image",
    "ImageError",
    "MissingWaylandGlobalError",
    "Renderer",
    "RendererError",
    "Shader",
    "ShaderError",
    "Target",
    "WallpaperSurface",
    "WallpaperSurfaceError",
    "WaylandGlobals",
    "WaylandUnavailableError",
    "connect",
    "create",
    "create_wallpaper",
    "discover_globals",
]
