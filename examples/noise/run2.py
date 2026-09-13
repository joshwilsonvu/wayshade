"""Renders TV static/snow/noise."""

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "wayshade @ git+https://github.com/joshwilsonvu/wayshade",
# ]
# ///

import wayshade

with wayshade.create() as renderer:
    noise_shader = renderer.load_shader_file("./noise2.glsl")

    def update(frame: wayshade.Frame) -> None:
        noise_shader.set("iTime", frame.time)
        renderer.draw(noise_shader, to=renderer.wallpaper, max_fps=12)

    renderer.run(update=update)
