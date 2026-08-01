# Wayshade Implementation Plan

## What and why

Wayshade is a small Python-controlled renderer for shader wallpapers on Linux/Wayland.

Shader wallpapers are a compelling way to make a desktop feel personal and alive, but existing tools tend to force users into one of two unsatisfying models: a fixed application with a narrow set of built-in features, or a low-level graphics environment that requires far more setup than a wallpaper should.

Wayshade exists to sit between those extremes. It should be as easy to assemble as a small configuration file, while remaining a real Python program whose behavior can be extended without waiting for the wallpaper engine to add a feature. A user should be able to combine a shader with local images, system state, network data, procedural logic, or any other Python-accessible information, then decide exactly how those inputs flow through the rendering pipeline.

The core philosophy is **a minimal rendering API with maximum scriptability**:

- the library handles the difficult platform work: GPU rendering, textures, frame pacing, and Wayland wallpaper presentation;
- the user controls the meaningful application logic: data collection, timing, composition, and shader inputs;
- the common path stays short and approachable;
- advanced behavior emerges from explicit primitives rather than an increasingly large configuration language.

This is deliberately not primarily a Shadertoy runner, a YAML wallpaper format, or a catalog of ambient-data integrations. Those may be useful adapters later, but the central product is a programmable wallpaper renderer that lets the user own the pipeline.

## 1. Features

The common case should be a short script that:

1. loads a fragment GLSL shader;
2. loads one or more images as textures;
3. updates arbitrary uniforms from Python;
4. renders to a monitor wallpaper surface.

The advanced case should let the script control the rendering pipeline without the library imposing a domain-specific configuration format. Users can use arbitrary Python to gather data from the system, files, networks, sensors, APIs, or other programs, then connect that data to shader uniforms.

The library should provide a layered API:

- a compact path for ordinary shader wallpapers;
- explicit lower-level primitives for shader state, images, render buffers, destinations, and drawing;
- convenience features such as Shadertoy compatibility only after the core model is stable.

The project is Wayland-specific. Cross-platform rendering is not a goal.

## 2. Non-goals for the first version

The first version will not attempt to provide:

- a YAML or other declarative wallpaper format;
- a general windowing toolkit;
- custom vertex shaders or arbitrary geometry;
- broad GLSL compatibility across every OpenGL profile;
- Shadertoy compatibility;
- a built-in catalog of ambient/system data;
- automatic shader translation between GLSL and WGSL;
- seamless monitor hotplug and layout migration;
- a normal-window fallback when wallpaper layer-shell support is unavailable;
- a required multiprocess or daemon architecture.

The user’s Python process is the application. Wayshade owns the graphics and Wayland presentation path, but does not own the user’s data-gathering logic.

## 3. Rendering model

The first implementation targets a single monitor and a fullscreen fragment shader over library-provided geometry.

There are three important resource concepts:

### `Shader`

A compiled fragment GLSL shader using the supported backend profile. The library supplies the fullscreen vertex stage and geometry. Users do not need to write vertex shaders in the first version.

A shader owns mutable uniform state:

```python
shader.set("u_time", time.monotonic())
shader.set({
    "u_resolution": (1920, 1080),
    "u_exposure": 1.2,
})
```

Uniform values are persistent until changed. `draw()` consumes the shader’s current state.

### `Image`

An `Image` is readable by shaders and writable by draw operations. It may be:

- loaded from an image file or memory;
- an intermediate GPU buffer created by `draw()`;
- used as a texture in a later draw;
- rescaled when used as a source for a destination of another size.

An image should abstract away the underlying texture/framebuffer details while retaining dimensions and an appropriate format.

### `Target`

A `Target` is a writable destination. The first target is the Wayland wallpaper surface:

```python
waypaper.wallpaper
```

A wallpaper target is not readable by shaders. It represents presentation to a monitor, not an intermediate texture.

Eventually, each monitor will have its own target. A convenience operation may write an image to every monitor, but multi-monitor routing is not part of the first implementation.

## 4. Fundamental draw operation

`draw()` is the core rendering primitive. It should support both shader draws and direct image presentation.

Conceptually:

```python
image = waypaper.draw(
    shader,
    textures={"u_moon": moon},
)

image = waypaper.draw(
    shader_b,
    textures={"input": image},
)

waypaper.draw(
    shader_c,
    textures={"input": image},
    to=waypaper.wallpaper,
)
```

If `to` is omitted, `draw()` allocates and returns a new `Image` buffer. This provides multipass composition without a separate multipass API.

If `to` is supplied, `draw()` renders into that writable target and returns no image result:

```python
waypaper.draw(shader, to=waypaper.wallpaper)
```

The API should also support presenting or copying an image directly:

```python
waypaper.draw(image, to=waypaper.wallpaper)
```

The exact function signatures may change during the graphics spike, but these semantics should remain stable:

- shader source and image inputs are explicit;
- textures are passed in a separate `textures` mapping;
- destinations are explicit through `to` when needed;
- omitted `to` means “produce an intermediate `Image`.”

## 5. Proposed user-facing shape

The implementation should be designed around an explicit renderer/session object so that future multi-monitor support does not depend on process-global state:

```python
import waypaper

renderer = waypaper.create(output=0)
wallpaper = renderer.wallpaper

moon = renderer.load_image("moon.jpg")
shader = renderer.load_shader_file("moon.frag")

shader.set({
    "u_time": 0.0,
    "u_resolution": (1920, 1080),
})

renderer.draw(
    shader,
    textures={"u_moon": moon},
    to=wallpaper,
)
```

The library may additionally expose module-level convenience functions backed by a default renderer:

```python
waypaper.init(output=0)
moon = waypaper.load_image("moon.jpg")
shader = waypaper.load_shader_file("moon.frag")
waypaper.draw(shader, textures={"u_moon": moon})
```

However, the explicit renderer/session is the architectural foundation. A module-level default must not prevent multiple renderer instances or per-output state later.

The first API should prioritize string and file-based shader construction:

```python
shader = renderer.load_shader("""
#version 330

uniform float u_time;
uniform vec2 u_resolution;
uniform sampler2D u_moon;

out vec4 frag_color;

void main() {
    vec2 uv = gl_FragCoord.xy / u_resolution;
    frag_color = texture(u_moon, uv);
}
""")

shader = renderer.load_shader_file("moon.frag")
```

Only fragment shader source is user-provided initially. The supported GLSL version/profile and shader interface conventions must be documented and tested.

## 6. Render-loop model

Users may own the loop:

```python
while True:
    shader.set("u_time", time.monotonic())
    renderer.draw(shader, textures={"u_moon": moon})
```

The library also provides a convenience loop:

```python
def update(frame):
    shader.set({
        "u_time": frame.time,
        "u_delta_time": frame.delta_time,
    })
    renderer.draw(shader, textures={"u_moon": moon})

renderer.run(update=update)
```

`run()` is only a loop helper. `draw()` should use compositor frame callbacks when available and should not force users to gather data at the render rate. The user controls how often expensive data is refreshed; the callback may retain or reuse previously collected values.

The first implementation should define a clear frame object containing at least:

- monotonic elapsed time;
- delta time;
- output dimensions;
- output identity/index where available.

Automatic uniforms are not implicit. A later explicit helper may be provided, such as:

```python
shader.default_uniforms(time=True, resolution=True, delta_time=True)
```

but the base API must not silently inject names or values into user shaders.

## 7. Wayland integration

The first target is a single fullscreen background surface using `wlr-layer-shell-unstable-v1`.

The surface should:

- attach to the background layer;
- anchor to all four edges of the selected output;
- remain behind normal application windows and overlays;
- use compositor frame callbacks for presentation scheduling;
- expose its dimensions to the renderer;
- fail clearly if the compositor does not advertise the required layer-shell protocol.

The first output-selection behavior is:

- default to the primary/first available output;
- accept a numeric output index such as `output=0` or `output=2`;
- defer output-name selection and full monitor routing until the single-output path is reliable.

Niri is the primary development compositor. Sway and Hyprland are compatibility targets because they provide useful layer-shell coverage. Compatibility depends on compositor support for the relevant protocol; the project should not promise support on arbitrary Wayland compositors that lack it.

Monitor hotplug/layout changes are outside the first implementation. A later design may recreate per-output state or rerun an application factory, but arbitrary user code must not be silently rerun because doing so can duplicate side effects.

If an application is fullscreen, `draw()` should block until the application is windowed again, so as not to consume system resources when the wallpaper wouldn't be visible anyway.

## 8. Graphics backend decision

Do not commit to WebGPU merely because the original draft proposed it. The requirements now favor a backend with strong support for:

- ordinary fragment GLSL;
- fullscreen rendering;
- 2D textures and image loading;
- framebuffer/render-image objects;
- sampling intermediate images;
- GPU-backed Wayland presentation through EGL or an equivalent native path.

The first implementation milestone is a graphics/Wayland feasibility spike:

1. connect to Wayland;
2. create a layer-shell background surface on Niri;
3. establish a GPU-backed rendering context;
4. render a fullscreen solid color or triangle/quad;
5. present it through compositor frame callbacks;
6. verify that the surface behaves as a wallpaper behind application windows;
7. render at least one offscreen image and sample it in a later draw.

Candidate backends may include an OpenGL/EGL-based Python binding or another library that exposes the required native surface integration. Vulkan and WebGPU should be considered only if they materially simplify the complete path. The choice must be based on a working prototype, not API preference alone.

The chosen backend must document its native dependencies. Pure-Python Wayland bindings do not eliminate native GPU driver, EGL/OpenGL, or backend requirements.

## 9. Image and shader requirements

### Images

The initial image loader should support common formats through an existing image library, at minimum:

- PNG;
- JPEG;
- WebP if supported without disproportionate complexity.

Images should be converted to a predictable GPU format, initially RGBA8. The implementation should define:

- filtering behavior;
- edge addressing behavior;
- alpha handling;
- orientation conventions;
- color-space assumptions;
- rescaling behavior when source and destination dimensions differ.

Texture reload/watch functionality is not required for the first version.

### Shaders

The first shader contract should support:

- ordinary fragment GLSL;
- scalar and vector uniforms;
- sampler2D texture uniforms;
- a library-provided fullscreen vertex stage;
- compilation errors with useful source locations;
- explicit output color.

The implementation should validate or report unsupported uniforms and texture bindings rather than silently ignoring them.

Shadertoy support is a future adapter. It should not shape the core API or make Shadertoy’s predefined pipeline assumptions part of the base shader contract.

## 10. Package and distribution strategy

Use a conventional Python package as the source of truth, with a `pyproject.toml` and normal dependency metadata. This supports both:

```sh
pip install wayshade
```

and:

```sh
uv add wayshade
```

PEP 723 should be used for standalone examples and user scripts where it improves the “run this file” experience:

```sh
uv run wallpaper.py
```

The package should not require users to use `uv`, but `uv` can be the recommended tool for examples and development. Native graphics requirements and GPU drivers must be documented honestly.

## 11. Implementation phases

### Phase 0: Graphics feasibility spike

- Select the initial Wayland protocol binding.
- Create and configure a layer-shell surface on Niri.
- Establish a GPU-backed Wayland rendering path.
- Present a solid color using compositor frame callbacks.
- Verify output selection and surface layering.
- Render to an offscreen image and sample it in a second draw if the backend supports the intended model.

Do not build the public API around a backend that cannot complete this phase cleanly.

### Phase 1: Single-output rendering core

- Create an explicit renderer/session object.
- Implement output selection by default/primary output and numeric index.
- Implement `Target` for the wallpaper surface.
- Implement fragment shader loading from strings and files.
- Implement fullscreen rendering.
- Implement shader uniform state and scalar/vector values.
- Implement compositor-driven presentation.

### Phase 2: Images and composition

- Load image files into GPU-readable `Image` objects.
- Bind images as sampler2D textures.
- Implement image-to-target drawing with rescaling.
- Implement omitted-`to` draws that produce readable/writable `Image` buffers.
- Implement shader-to-image and image-to-shader composition.
- Add cleanup and resource lifetime handling.

### Phase 3: Loop helper and usability

- Add `renderer.run(update=...)`.
- Define the frame object and timing behavior.
- Add optional explicit default-uniform helpers.
- Improve shader and texture error messages.
- Provide minimal PEP 723 examples.
- Add a static image, procedural shader, and textured shader example.

### Phase 4: Compatibility and multi-output research

Only after the single-output path is stable:

- test sway and Hyprland;
- enumerate outputs and expose stable output metadata;
- give each output a `Target`;
- define per-output rendering semantics;
- add a convenience operation to draw an image to all outputs;
- decide whether application factories or another lifecycle model are needed for hotplug.

### Later possibilities

- Shadertoy adapter;
- shader file hot reload;
- richer sampler configuration;
- additional image formats and color management;
- explicit asynchronous data/update helpers;
- optional custom vertex/geometry support if a real use case appears.

## 12. Testing and validation

The first validation priority is manual compositor testing because the critical integration is graphics backend plus Wayland layer shell.

### Required early checks

- surface appears behind application windows;
- surface covers the selected output;
- frame callbacks do not busy-loop;
- a static image remains displayed when no new draw occurs;
- animated shader updates at the compositor’s requested cadence;
- shader compilation failures identify the relevant source location;
- missing image files and unsupported formats fail clearly;
- an image can be sampled by a shader;
- an intermediate image can be rendered into and sampled by a later draw;
- resources can be released without crashes or persistent GPU/Wayland objects.

### Compatibility targets

- Niri first;
- Sway next;
- Hyprland after the core path is stable.

### Performance goals

Do not enforce arbitrary memory or CPU limits before measuring a working implementation. Instead, record:

- CPU use for a static image;
- CPU use for a simple animated shader;
- frame pacing;
- memory usage over a long run;
- behavior after several hours of rendering;
- GPU memory use for one or more intermediate images.

A stable 24-hour run and low CPU use for simple GPU-bound shaders are validation goals, not assumptions to encode into the initial API.

## 13. Initial success criteria

The first useful release succeeds if a user can:

1. install the package with `pip` or `uv`;
2. run a small Python script on Niri;
3. create a fullscreen GLSL shader from an inline string or `.frag` file;
4. load a JPG or PNG as a texture;
5. update arbitrary shader uniforms from Python;
6. render the shader as a proper background wallpaper on one output;
7. render an intermediate `Image` and feed it into another shader;
8. optionally use `run(update=...)` for compositor-paced animation;
9. receive actionable errors when the compositor, shader, or image cannot be used.

Multi-monitor rendering, Shadertoy compatibility, hot reload, and broader compositor coverage come after these fundamentals work.
