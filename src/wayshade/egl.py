"""Small EGL/Wayland presentation bridge for the Phase 0 spike."""

from __future__ import annotations

import ctypes
from dataclasses import dataclass
from typing import Any


class EglUnavailableError(RuntimeError):
    """Raised when EGL or the Wayland-EGL bridge cannot be loaded."""


class EglPresentationError(RuntimeError):
    """Raised when an EGL object cannot be created or used."""


def _address(pointer: Any) -> int:
    """Return the integer address of a PyWayland CFFI pointer."""

    try:
        from pywayland import ffi

        address = int(ffi.cast("uintptr_t", pointer))  # type: ignore[arg-type]
    except (ImportError, TypeError, ValueError) as error:
        raise EglPresentationError(
            "Could not access a native Wayland pointer"
        ) from error
    if not address:
        raise EglPresentationError("Wayland supplied a null native pointer")
    return address


@dataclass
class EglPresenter:
    """An EGL window surface backed by a configured Wayland surface."""

    display: Any
    surface: Any
    width: int
    height: int
    egl_display: Any = None
    egl_context: Any = None
    egl_surface: Any = None
    egl_config: Any = None
    wl_window: Any = None
    _egl: Any = None
    _gl: Any = None
    _wayland_egl: Any = None
    closed: bool = False

    def __post_init__(self) -> None:
        self._create()

    def _create(self) -> None:
        try:
            self._egl = _load_egl()
            self._gl = _load_gl()
            self._wayland_egl = ctypes.CDLL("libwayland-egl.so.1")
        except (AttributeError, OSError, ImportError) as error:
            raise EglUnavailableError(
                "EGL presentation requires libEGL, libGL, and libwayland-egl"
            ) from error

        bridge = self._wayland_egl
        bridge.wl_egl_window_create.argtypes = [
            ctypes.c_void_p,
            ctypes.c_int,
            ctypes.c_int,
        ]
        bridge.wl_egl_window_create.restype = ctypes.c_void_p
        bridge.wl_egl_window_destroy.argtypes = [ctypes.c_void_p]
        bridge.wl_egl_window_destroy.restype = None

        native_surface = ctypes.c_void_p(_address(self.surface._ptr))
        self.wl_window = bridge.wl_egl_window_create(
            native_surface, self.width, self.height
        )
        if not self.wl_window:
            raise EglPresentationError("wl_egl_window_create failed")

        try:
            native_display = ctypes.c_void_p(_address(self.display._ptr))
            self.egl_display = self._egl.eglGetDisplay(native_display)
            if self.egl_display == self._egl.EGL_NO_DISPLAY:
                raise self._error("eglGetDisplay")

            major, minor = ctypes.c_int(), ctypes.c_int()
            if not self._egl.eglInitialize(self.egl_display, major, minor):
                raise self._error("eglInitialize")

            attributes = [
                self._egl.EGL_SURFACE_TYPE,
                self._egl.EGL_WINDOW_BIT,
                self._egl.EGL_RENDERABLE_TYPE,
                self._egl.EGL_OPENGL_BIT,
                self._egl.EGL_RED_SIZE,
                8,
                self._egl.EGL_GREEN_SIZE,
                8,
                self._egl.EGL_BLUE_SIZE,
                8,
                self._egl.EGL_ALPHA_SIZE,
                8,
                self._egl.EGL_NONE,
            ]
            config = (self._egl.EGLConfig * 1)()
            count = ctypes.c_int()
            if (
                not self._egl.eglChooseConfig(
                    self.egl_display, attributes, config, 1, count
                )
                or count.value == 0
            ):
                raise self._error("eglChooseConfig")
            self.egl_config = config[0]

            if not self._egl.eglBindAPI(self._egl.EGL_OPENGL_API):
                raise self._error("eglBindAPI")
            self.egl_context = self._egl.eglCreateContext(
                self.egl_display, self.egl_config, self._egl.EGL_NO_CONTEXT, None
            )
            if self.egl_context == self._egl.EGL_NO_CONTEXT:
                raise self._error("eglCreateContext")

            self.egl_surface = self._egl.eglCreateWindowSurface(
                self.egl_display, self.egl_config, self.wl_window, None
            )
            if self.egl_surface == self._egl.EGL_NO_SURFACE:
                raise self._error("eglCreateWindowSurface")
            if not self._egl.eglMakeCurrent(
                self.egl_display,
                self.egl_surface,
                self.egl_surface,
                self.egl_context,
            ):
                raise self._error("eglMakeCurrent")
        except Exception:
            self.close()
            raise

    def _error(self, operation: str) -> EglPresentationError:
        code = self._egl.eglGetError()
        return EglPresentationError(f"{operation} failed (EGL error 0x{code:04x})")

    def clear_and_swap(self, color: tuple[float, float, float, float]) -> None:
        """Clear the wallpaper to ``color`` and present one frame."""

        if self.closed:
            raise EglPresentationError("EGL presenter is closed")
        self._gl.glClearColor(*color)
        self._gl.glClear(self._gl.GL_COLOR_BUFFER_BIT)
        if not self._egl.eglSwapBuffers(self.egl_display, self.egl_surface):
            raise self._error("eglSwapBuffers")

    def offscreen_test_and_swap(self) -> None:
        """Render a texture-backed test image, sample it, and present it.

        This is deliberately a backend feasibility probe, not the public image
        API. It verifies the texture/FBO/shader path before that API is built.
        """

        if self.closed:
            raise EglPresentationError("EGL presenter is closed")
        gl = self._gl
        texture = gl.glGenTextures(1)
        framebuffer = gl.glGenFramebuffers(1)
        vertex_buffer = gl.glGenBuffers(1)
        program = 0
        shader_objects: list[int] = []
        try:
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D,
                0,
                gl.GL_RGBA,
                self.width,
                self.height,
                0,
                gl.GL_RGBA,
                gl.GL_UNSIGNED_BYTE,
                None,
            )
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, framebuffer)
            gl.glFramebufferTexture2D(
                gl.GL_FRAMEBUFFER,
                gl.GL_COLOR_ATTACHMENT0,
                gl.GL_TEXTURE_2D,
                texture,
                0,
            )
            if (
                gl.glCheckFramebufferStatus(gl.GL_FRAMEBUFFER)
                != gl.GL_FRAMEBUFFER_COMPLETE
            ):
                raise EglPresentationError("Offscreen framebuffer is incomplete")

            gl.glViewport(0, 0, self.width, self.height)
            gl.glClearColor(0.08, 0.08, 0.12, 1.0)
            gl.glClear(gl.GL_COLOR_BUFFER_BIT)

            vertex_source = """
                #version 120
                attribute vec2 position;
                varying vec2 uv;
                void main() {
                    uv = position * 0.5 + 0.5;
                    gl_Position = vec4(position, 0.0, 1.0);
                }
            """
            fragment_source = """
                #version 120
                uniform sampler2D source;
                varying vec2 uv;
                void main() {
                    gl_FragColor = texture2D(source, uv);
                }
            """
            for shader_type, source in (
                (gl.GL_VERTEX_SHADER, vertex_source),
                (gl.GL_FRAGMENT_SHADER, fragment_source),
            ):
                shader = gl.glCreateShader(shader_type)
                gl.glShaderSource(shader, source)
                gl.glCompileShader(shader)
                if not gl.glGetShaderiv(shader, gl.GL_COMPILE_STATUS):
                    log = gl.glGetShaderInfoLog(shader).decode(errors="replace")
                    raise EglPresentationError(
                        f"Offscreen shader compilation failed: {log}"
                    )
                shader_objects.append(shader)

            program = gl.glCreateProgram()
            for shader in shader_objects:
                gl.glAttachShader(program, shader)
            gl.glBindAttribLocation(program, 0, "position")
            gl.glLinkProgram(program)
            if not gl.glGetProgramiv(program, gl.GL_LINK_STATUS):
                log = gl.glGetProgramInfoLog(program).decode(errors="replace")
                raise EglPresentationError(f"Offscreen shader link failed: {log}")

            vertices = (ctypes.c_float * 8)(-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vertex_buffer)
            gl.glBufferData(
                gl.GL_ARRAY_BUFFER, ctypes.sizeof(vertices), vertices, gl.GL_STATIC_DRAW
            )
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            gl.glViewport(0, 0, self.width, self.height)
            gl.glUseProgram(program)
            gl.glActiveTexture(gl.GL_TEXTURE0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            gl.glUniform1i(gl.glGetUniformLocation(program, "source"), 0)
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, False, 0, None)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glDisableVertexAttribArray(0)
            if not self._egl.eglSwapBuffers(self.egl_display, self.egl_surface):
                raise self._error("eglSwapBuffers")
        finally:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            if program:
                gl.glDeleteProgram(program)
            for shader in shader_objects:
                gl.glDeleteShader(shader)
            gl.glDeleteBuffers(1, [vertex_buffer])
            gl.glDeleteFramebuffers(1, [framebuffer])
            gl.glDeleteTextures(1, [texture])

    def close(self) -> None:
        """Destroy EGL objects, then the native Wayland-EGL window."""

        if self.closed:
            return
        if self._egl is not None and self.egl_display not in (
            None,
            self._egl.EGL_NO_DISPLAY,
        ):
            if self.egl_context not in (None, self._egl.EGL_NO_CONTEXT):
                self._egl.eglMakeCurrent(
                    self.egl_display,
                    self._egl.EGL_NO_SURFACE,
                    self._egl.EGL_NO_SURFACE,
                    self._egl.EGL_NO_CONTEXT,
                )
            if self.egl_surface not in (None, self._egl.EGL_NO_SURFACE):
                self._egl.eglDestroySurface(self.egl_display, self.egl_surface)
            if self.egl_context not in (None, self._egl.EGL_NO_CONTEXT):
                self._egl.eglDestroyContext(self.egl_display, self.egl_context)
            self._egl.eglTerminate(self.egl_display)
        if self.wl_window and self._wayland_egl is not None:
            self._wayland_egl.wl_egl_window_destroy(self.wl_window)
        self.closed = True


def _load_egl() -> Any:
    from OpenGL import EGL

    return EGL


def _load_gl() -> Any:
    from OpenGL import GL

    return GL


__all__ = ["EglPresentationError", "EglPresenter", "EglUnavailableError"]
