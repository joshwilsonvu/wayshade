#version 120

uniform float iTime;
varying vec2 uv;

void main() {
  float a = clamp(pow(fract(sin(dot(uv * 0.05, vec2(12.9898, 78.233) * iTime)) * 438.5453) * 1.9, 40), 0, 1);
  gl_FragColor = vec4(vec3(a) * 0.5 + 0.2, 1.0);
}
