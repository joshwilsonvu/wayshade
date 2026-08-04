"""Exercise two shader passes with an intermediate Image target."""

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
    intermediate = renderer.draw(brighten, textures={"source": source})

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
    renderer.draw(vignette, textures={"source": intermediate}, to=renderer.wallpaper)
    input("Press Enter to quit")
