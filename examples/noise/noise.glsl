#version 120

uniform float iTime;
uniform vec2 iResolution;
varying vec2 uv;

uniform float vsync_issues;
uniform vec2 mouse_pos;

float noise(float time, vec2 st) {
  return fract(
    sin(dot(st * vsync_issues, vec2(time, time * 13352.0) * mouse_pos)) * 8282.0
  );
}

void main() {
  // Direct port of Godot's UV / (1.0 / SCREEN_PIXEL_SIZE.xy).
  vec2 st = (uv - 0.5) * iResolution;
  // vec2 st = uv;

  gl_FragColor = vec4(vec3(noise(iTime, st)), 1.0);
}
