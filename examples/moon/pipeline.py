"""Exercise two shader passes with an intermediate Image target."""

# /// script
# requires-python = ">=3.13"
# dependencies = [
#     "wayshade @ git+https://github.com/joshwilsonvu/wayshade",
# ]
# ///

import wayshade

with wayshade.create() as renderer:
    source = renderer.load_image("moon.jpg")

    brighten = renderer.load_shader(
        """
        #version 120
        uniform sampler2D source;
        varying vec2 uv;

        void main() {
            vec4 color = texture2D(source, uv);
            gl_FragColor = vec4(min(color.rgb * 1.25, 1.0), color.a);
        }
        """
    )
    brighten.set("source", source)
    intermediate = renderer.draw(brighten)

    vignette = renderer.load_shader(
        """
        #version 120
        uniform sampler2D source;
        varying vec2 uv;

        void main() {
            vec2 centered = uv - vec2(0.5);
            float edge = 1.0 - 0.5 * 4 * dot(centered, centered);
            vec4 color = texture2D(source, uv);
            gl_FragColor = vec4(color.rgb * edge, color.a);
        }
        """
    )
    vignette.set("source", intermediate)
    renderer.draw(vignette, to=renderer.wallpaper)
    input("Press Enter to quit")
