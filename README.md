# Wayshade

Wayshade is a Python-controlled shader wallpaper renderer for Linux/Wayland.
It provides a small rendering API while leaving application logic—data gathering,
timing, composition, and uniform updates—in the user's Python process.

The project is intentionally Wayland-specific. It targets a single fullscreen
background surface first, using `wlr-layer-shell-unstable-v1`, EGL/OpenGL, and
Pillow. It is not a general windowing toolkit, a YAML wallpaper format, or a
Shadertoy runner.

## Development environment

The project uses Python 3.13, [uv](https://docs.astral.sh/uv/), and a project-local
`.venv`. The repository also includes a Nix development flake and direnv
integration.

With Nix and direnv:

```sh
direnv allow
cd /path/to/wayshade
```

Without direnv:

```sh
nix develop
```

Then install/synchronize Python dependencies and run the checks:

```sh
uv sync
uv run pytest
uv run ruff check .
```

The development shell provides Python, uv, Wayland libraries, protocol XML, and
the protocol scanner. It scopes the Wayland library path to this project. It does
not provide or select an OpenGL driver: driver selection belongs to the host
distribution, and Wayshade does not require a `nixGL` wrapper.

A live compositor session is required for Wayland/EGL validation. Niri is the
primary development compositor; Sway and Hyprland are later compatibility
targets. The compositor must advertise `wlr-layer-shell-unstable-v1`.

End users need:

- a Wayland client runtime;
- EGL and OpenGL libraries;
- a working host OpenGL driver;
- a compositor implementing layer shell.

The generated layer-shell bindings are included in `src/wayshade/_protocol/`, so
end users do not need the `wlr-protocols` XML package installed.

## Current API

The public API is centered on an explicit `Renderer` session:

```python
import time

import wayshade

with wayshade.create(output=0) as renderer:
    image = renderer.load_image("moon.jpg")
    shader = renderer.load_shader(
        """
        #version 120
        uniform sampler2D source;
        uniform float u_time;
        varying vec2 uv;

        void main() {
            vec4 color = texture2D(source, uv);
            float pulse = 0.8 + 0.2 * sin(u_time);
            gl_FragColor = vec4(color.rgb * pulse, color.a);
        }
        """
    )

    shader.set({"time": time.monotonic(), "source": image})
    renderer.draw(shader, to=renderer.wallpaper)
```

Important public objects:

- `Renderer`: owns one Wayland wallpaper target and its graphics session.
- `Target`: writable destination abstraction; the current public target is the
  wallpaper surface.
- `WallpaperSurface`: low-level configured layer-shell surface.
- `Shader`: fragment GLSL source plus persistent scalar/vector and image uniform state.
- `Image`: RGBA8 image loaded from disk or allocated as an intermediate buffer.
- `Frame`: timing and output data passed to `Renderer.run()`.

### Drawing

`Renderer.draw()` accepts either a `Shader` or an `Image`:

```python
# Shader to wallpaper.
shader.set("source", image)
renderer.draw(shader, to=renderer.wallpaper)

# Shader to a new intermediate image.
intermediate = renderer.draw(shader)

# Sample that intermediate in a later pass.
other_shader.set("input", intermediate)
renderer.draw(other_shader, to=renderer.wallpaper)

# Direct image presentation.
renderer.draw(image, to=renderer.wallpaper)
```

If `to` is omitted, a new `Image` with the wallpaper dimensions is allocated and
returned. `Image` objects are readable as shader textures and writable as draw
destinations. The current image behavior is:

- PNG, JPEG, WebP, and other Pillow-supported formats can be loaded;
- loaded images are converted to predictable RGBA8 pixels;
- textures use linear filtering;
- texture edges use clamp-to-edge addressing;
- image textures and framebuffers are allocated lazily on first GPU use;
- source and destination sizes may differ, with fullscreen texture coordinates
  providing the rescaling behavior.
- each image-valued uniform consumes one fragment texture unit; the practical
  maximum is reported by the OpenGL driver and is typically at least 16.

### Uniforms

Uniform state persists on a `Shader` until changed. Wayshade does not inject
standard or default uniforms: the application chooses names that match its GLSL
source and passes values explicitly. Scalar and vector values are uploaded as
ordinary GLSL uniforms; an `Image` value is bound as a `sampler2D` texture.
`Shader.set()` is the only uniform/binding API.

```python
shader.set("amount", 1.25)
shader.set({
    "resolution": (renderer.wallpaper.width, renderer.wallpaper.height),
    "tint": (1.0, 0.5, 0.25),
    "source": image,
})
```

Supported values are booleans, integers, floats, and numeric tuples of one to
four elements. Uniform names and sampler names are checked during drawing;
missing or inactive names produce an error rather than being silently ignored.

Only the fragment shader is user-provided. The renderer supplies a fullscreen
vertex shader and quad. The current GLSL contract uses the compatibility-style
`#version 120` interface (`attribute`, `varying`, `texture2D`, and
`gl_FragColor`).

### Compositor-paced animation

`Renderer.run()` calls an update function once per compositor-paced frame. The
application can copy the frame values into its shader uniforms explicitly:

```python
def update(frame: wayshade.Frame) -> None:
    shader.set(frame.uniforms())
    renderer.draw(shader, to=renderer.wallpaper)

renderer.run(update=update)
```

`Frame.uniforms()` returns a fresh plain dictionary containing `time`,
`delta_time`, `width`, and `height`, plus `output` when a numeric output was
selected. It is a convenience for explicit uniform updates, not an implicit
shader contract; applications may rename or select values before calling
`Shader.set()`.

`Frame` contains:

- `time`: monotonic elapsed seconds since `run()` started;
- `delta_time`: seconds since the previous update;
- `width` and `height`: selected output dimensions;
- `output`: the numeric output index supplied to `create()`, if any.

The first update runs immediately. Later updates wait for the previous draw's
Wayland frame callback; the loop does not busy-loop. Returning `False` from the
callback stops the loop. `Renderer.run()` also handles Ctrl-C and restores the
caller's original SIGINT handler, including when the interruption occurs while
PyWayland is blocked in native dispatch.

## Examples

The examples in `examples/moon/` require a live compositor session. From that
directory:

```sh
python image.py       # direct image presentation
python texture.py     # image -> intermediate -> wallpaper
python uniform.py     # inline shader, sampler, scalar/vector uniforms
python pipeline.py    # two shader passes through an intermediate image
python run.py         # compositor-paced rainbow tint animation
```

`run.py` loads the moon image, updates a rainbow tint from `Frame.time`, and exits
cleanly on Ctrl-C. The static examples wait for Enter before exiting.

A later usability task will add minimal PEP 723 metadata so representative
examples can also be run with `uv run --script`. PEP 723 covers Python
dependencies only; the Wayland compositor, EGL libraries, and OpenGL driver
remain system prerequisites.

## Architecture and constraints

The important ownership/lifetime rules are:

1. `Renderer` owns the wallpaper session and tracks intermediate `Image` objects.
2. `WallpaperSurface` owns the Wayland layer surface and lazily-created
   `EglPresenter`.
3. `EglPresenter` owns the EGL display/context/surface and GPU resources.
4. Shader programs are cached by fragment source for the lifetime of one EGL
   presenter/context.
5. Cached programs, image framebuffers, and image textures must be deleted while
   the EGL context is still current and before EGL termination.
6. Pending Wayland frame callbacks must be destroyed before the Wayland objects
   they belong to.
7. There is no normal-window fallback and no process-global default renderer.

The first output is selected by default. Numeric selection is supported through
`create(output=0)` and `create_wallpaper(output=0)`. Output names, hotplug,
layout migration, and multi-monitor routing are intentionally deferred.

## Forward plan

The graphics feasibility spike and the single-output rendering/image pipeline are
complete. Shader program caching, explicit `Frame` timing, the compositor-paced
`run()` helper, and runnable image/shader examples are also implemented.

The initial Phase 3 loop and usability work is complete. The project explicitly
leaves uniform naming and selection to the application; there is no renderer
managed default-uniform contract. `Frame.uniforms()` provides an optional plain
dictionary convenience for copying loop values into a shader.

The next work should continue Phase 3 in this order:

### 1. Improve shader and texture diagnostics

Make failures actionable for users:

- include the shader source path when a file-loaded shader fails;
- preserve useful GLSL compiler source locations and logs;
- distinguish compilation, linking, uniform, sampler, texture, and framebuffer
  failures;
- report the image path and dimensions for image-loading/upload failures;
- test missing files, unsupported formats, inactive uniforms, failed shader
  compilation, failed linking, and incomplete framebuffers.

Avoid hiding driver logs or replacing useful backend errors with generic messages.

### 2. Add minimal PEP 723 examples

Add metadata to a small representative set of standalone scripts:

- a static image example;
- a procedural shader example;
- a textured animated example using `Renderer.run()`.

Determine the correct dependency declaration for the package's pre-release state
before editing the examples: if `wayshade` is not installable from an index, the
metadata must use the supported local-development workflow rather than claiming
that a clean external machine can install the unpublished package. Keep native
Wayland/EGL/OpenGL requirements documented separately.

Update the README commands and example comments after the metadata is validated
with `uv run --script`.

### 3. Strengthen GPU-path tests

Keep ordinary tests deterministic and compositor-independent, then add an
explicitly opt-in live validation path.

Deterministic fake-GL/backend coverage should verify:

- one cached program per distinct fragment source;
- cached program and image deletion before EGL termination;
- shader compilation and linking errors retain useful logs;
- scalar/vector uniform calls are selected correctly;
- missing sampler/uniform names fail clearly;
- image textures and framebuffers are allocated lazily;
- failed draws clean up temporary GL objects and frame callbacks.

The live compositor validation should be a script or separately marked test, not
part of the normal CI suite. On Niri it should verify EGL creation, wallpaper
presentation, image sampling, intermediate-image sampling, repeated cached draws,
frame pacing, Ctrl-C exit, and clean resource release.

### 4. Then investigate later compatibility work

Only after the single-output path and Phase 3 usability work are stable:

- test Sway and Hyprland;
- enumerate outputs and expose stable output metadata;
- provide one `Target` per output;
- define per-output rendering semantics;
- research hotplug lifecycle behavior.

Do not add multi-monitor routing, Shadertoy assumptions, shader hot reload, or a
normal-window fallback while the single-output contract is still changing.

## Validation checklist

For ordinary changes:

```sh
uv run pytest
uv run ruff check .
```

For a live compositor check:

```sh
uv run python -c \
  'from wayshade import create_wallpaper; w = create_wallpaper(); print(w.width, w.height); w.present_solid(); w.close()'
```

For the current examples, run from `examples/moon/` inside a compositor session.
The key manual checks are:

- the wallpaper is behind normal application windows;
- it covers the selected output;
- a static image remains displayed without repeated draws;
- animation follows compositor frame cadence;
- an image can be sampled by a shader;
- an intermediate image can be sampled by a later pass;
- Ctrl-C exits `run.py` without a CFFI traceback or hang;
- shader and image failures identify the relevant resource;
- repeated draws do not continuously compile new programs;
- closing the renderer releases EGL, GPU, and Wayland resources cleanly.

Do not claim live validation passed unless it was actually run against a compositor
and host GPU. The normal Python test suite cannot prove those integration points.
