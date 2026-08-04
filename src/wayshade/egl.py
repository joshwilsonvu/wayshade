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
    images: list[Any] = None  # type: ignore[assignment]
    _programs: dict[str, int] = None  # type: ignore[assignment]

    def __post_init__(self) -> None:
        self.images = []
        self._programs = {}
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

    def ensure_image(self, image: Any) -> None:
        """Create the texture and framebuffer backing an Image."""
        if image.texture is not None:
            return
        gl = self._gl
        texture = None
        framebuffer = None
        try:
            texture = gl.glGenTextures(1)
            gl.glBindTexture(gl.GL_TEXTURE_2D, texture)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MIN_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(gl.GL_TEXTURE_2D, gl.GL_TEXTURE_MAG_FILTER, gl.GL_LINEAR)
            gl.glTexParameteri(
                gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_S, gl.GL_CLAMP_TO_EDGE
            )
            gl.glTexParameteri(
                gl.GL_TEXTURE_2D, gl.GL_TEXTURE_WRAP_T, gl.GL_CLAMP_TO_EDGE
            )
            gl.glTexImage2D(
                gl.GL_TEXTURE_2D,
                0,
                gl.GL_RGBA,
                image.width,
                image.height,
                0,
                gl.GL_RGBA,
                gl.GL_UNSIGNED_BYTE,
                image.pixels,
            )
            framebuffer = gl.glGenFramebuffers(1)
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
                raise EglPresentationError("framebuffer is incomplete")
            image.texture = texture
            image.framebuffer = framebuffer
            self.images.append(image)
        except Exception as error:
            if framebuffer is not None:
                gl.glDeleteFramebuffers(1, [framebuffer])
            if texture is not None:
                gl.glDeleteTextures(1, [texture])
            label = _image_label(image)
            if isinstance(error, EglPresentationError):
                detail = str(error)
            else:
                detail = str(error) or error.__class__.__name__
            raise EglPresentationError(
                f"Image texture/framebuffer setup failed for {label}: {detail}"
            ) from error
        finally:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            gl.glBindTexture(gl.GL_TEXTURE_2D, 0)

    def _program_for(self, source: str, source_path: Any = None) -> int:
        """Compile and link ``source`` once for this EGL context."""
        if source in self._programs:
            return self._programs[source]
        gl = self._gl
        vertex_source = """
            #version 120
            attribute vec2 position;
            varying vec2 uv;
            void main() {
                uv = position * 0.5 + 0.5;
                gl_Position = vec4(position, 0.0, 1.0);
            }
        """
        shader_objects: list[int] = []
        program = 0
        try:
            for shader_type, shader_source in (
                (gl.GL_VERTEX_SHADER, vertex_source),
                (gl.GL_FRAGMENT_SHADER, source),
            ):
                shader_object = gl.glCreateShader(shader_type)
                gl.glShaderSource(shader_object, shader_source)
                gl.glCompileShader(shader_object)
                if not gl.glGetShaderiv(shader_object, gl.GL_COMPILE_STATUS):
                    log = gl.glGetShaderInfoLog(shader_object)
                    if isinstance(log, bytes):
                        log = log.decode(errors="replace")
                    kind = (
                        "fragment" if shader_type == gl.GL_FRAGMENT_SHADER else "vertex"
                    )
                    location = (
                        f" ({source_path})"
                        if kind == "fragment" and source_path
                        else ""
                    )
                    raise EglPresentationError(
                        f"{kind.capitalize()} shader compilation failed{location}: {log}"
                    )
                shader_objects.append(shader_object)

            program = gl.glCreateProgram()
            for shader_object in shader_objects:
                gl.glAttachShader(program, shader_object)
            gl.glBindAttribLocation(program, 0, "position")
            gl.glLinkProgram(program)
            if not gl.glGetProgramiv(program, gl.GL_LINK_STATUS):
                log = gl.glGetProgramInfoLog(program)
                if isinstance(log, bytes):
                    log = log.decode(errors="replace")
                location = f" ({source_path})" if source_path else ""
                raise EglPresentationError(f"Shader link failed{location}: {log}")
            self._programs[source] = program
            return program
        except Exception:
            if program:
                gl.glDeleteProgram(program)
            raise
        finally:
            for shader_object in shader_objects:
                gl.glDeleteShader(shader_object)

    def render_shader(
        self, shader: Any, textures: dict[str, Any], target: Any, *, swap: bool
    ) -> None:
        """Draw a public fragment shader fullscreen."""
        if self.closed:
            raise EglPresentationError("EGL presenter is closed")
        gl = self._gl
        vertex_buffer = gl.glGenBuffers(1)
        program = 0
        try:
            program = self._program_for(shader.source, shader.source_path)
            vertices = (ctypes.c_float * 8)(-1.0, -1.0, 1.0, -1.0, -1.0, 1.0, 1.0, 1.0)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, vertex_buffer)
            gl.glBufferData(
                gl.GL_ARRAY_BUFFER, ctypes.sizeof(vertices), vertices, gl.GL_STATIC_DRAW
            )
            framebuffer = 0
            width, height = self.width, self.height
            if not hasattr(target, "surface"):
                self.ensure_image(target)
                framebuffer = target.framebuffer
                width, height = target.width, target.height
            # Materialize source textures before binding the destination FBO:
            # ensure_image() restores the default framebuffer after allocation.
            for image in textures.values():
                self.ensure_image(image)
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, framebuffer)
            gl.glViewport(0, 0, width, height)
            gl.glUseProgram(program)
            for unit, (name, image) in enumerate(textures.items()):
                gl.glActiveTexture(gl.GL_TEXTURE0 + unit)
                gl.glBindTexture(gl.GL_TEXTURE_2D, image.texture)
                location = gl.glGetUniformLocation(program, name)
                if location < 0:
                    raise EglPresentationError(
                        f"Shader texture uniform {name!r} was not found or is not active"
                    )
                gl.glUniform1i(location, unit)
            for name, value in shader.uniforms.items():
                location = gl.glGetUniformLocation(program, name)
                if location < 0:
                    raise EglPresentationError(
                        f"Shader uniform {name!r} was not found or is not active"
                    )
                _set_uniform(gl, location, value)
            gl.glEnableVertexAttribArray(0)
            gl.glVertexAttribPointer(0, 2, gl.GL_FLOAT, False, 0, None)
            gl.glDrawArrays(gl.GL_TRIANGLE_STRIP, 0, 4)
            gl.glDisableVertexAttribArray(0)
            if not swap:
                # The next pass may sample this texture immediately. Flush the
                # offscreen draw before changing targets and binding it as input.
                gl.glFlush()
            if swap and not self._egl.eglSwapBuffers(
                self.egl_display, self.egl_surface
            ):
                raise self._error("eglSwapBuffers")
        finally:
            gl.glBindFramebuffer(gl.GL_FRAMEBUFFER, 0)
            gl.glBindBuffer(gl.GL_ARRAY_BUFFER, 0)
            gl.glDeleteBuffers(1, [vertex_buffer])

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
        if self._gl is not None:
            # Programs and images must be deleted while the EGL context is
            # current; terminating EGL first makes those deletes invalid.
            for program in self._programs.values():
                self._gl.glDeleteProgram(program)
            self._programs.clear()
            for image in self.images or []:
                if image.framebuffer is not None:
                    self._gl.glDeleteFramebuffers(1, [image.framebuffer])
                if image.texture is not None:
                    self._gl.glDeleteTextures(1, [image.texture])
                image.framebuffer = None
                image.texture = None
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


def _image_label(image: Any) -> str:
    source = getattr(image, "source", None)
    path = f"{source} " if source is not None else ""
    return f"{path}({image.width}x{image.height})"


def _set_uniform(gl: Any, location: int, value: Any) -> None:
    if isinstance(value, bool):
        gl.glUniform1i(location, int(value))
    elif isinstance(value, int):
        gl.glUniform1i(location, value)
    elif isinstance(value, float):
        gl.glUniform1f(location, value)
    elif len(value) == 1:
        gl.glUniform1f(location, float(value[0]))
    elif len(value) == 2:
        gl.glUniform2f(location, float(value[0]), float(value[1]))
    elif len(value) == 3:
        gl.glUniform3f(location, float(value[0]), float(value[1]), float(value[2]))
    elif len(value) == 4:
        gl.glUniform4f(
            location, float(value[0]), float(value[1]), float(value[2]), float(value[3])
        )
    else:
        raise EglPresentationError("Unsupported shader uniform value")


def _load_egl() -> Any:
    from OpenGL import EGL

    return EGL


def _load_gl() -> Any:
    from OpenGL import GL

    return GL


__all__ = ["EglPresentationError", "EglPresenter", "EglUnavailableError"]
