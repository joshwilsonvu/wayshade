"""Exercise inline shader loading and scalar/vector uniform updates."""

import wayshade

with wayshade.create() as renderer:
    image = renderer.load_image("moon.jpg")
    shader = renderer.load_shader(
        """
        #version 120
        uniform sampler2D u_moon;
        uniform float u_exposure;
        uniform vec3 u_tint;
        varying vec2 uv;

        void main() {
            vec4 color = texture2D(u_moon, uv);
            color.rgb *= u_exposure * u_tint;
            gl_FragColor = color;
        }
        """
    )
    shader.set({"u_exposure": 1.0, "u_tint": (1.0, 0.85, 0.75)})
    renderer.draw(shader, textures={"u_moon": image}, to=renderer.wallpaper)
    input("Press Enter to quit")
