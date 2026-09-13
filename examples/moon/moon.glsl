#version 120

uniform float iTime;
uniform sampler2D moon;
uniform vec2 iResolution;
varying vec2 uv;

// controls
#define DISTANCE true
#define STARS true
#define LIBRATION true
#define SURGE true
#define ANTIALIAS true

// constants
#define SUN_ROTATION 0.03
#define CAMERA_DISTANCE 2.8
#define AMBIENT 0.02
#define PERIGEE 362600.0
#define APOGEE 405400.0
#define PI 3.14159265359

// utils
vec3 rotateX(vec3 p, float a) {
  float c = cos(a), s = sin(a);
  return vec3(p.x, c * p.y - s * p.z, s * p.y + c * p.z);
}
vec3 rotateY(vec3 p, float a) {
  float c = cos(a), s = sin(a);
  return vec3(c * p.x + s * p.z, p.y, -s * p.x + c * p.z);
}
float hash(vec2 p) {
  p = fract(p * vec2(127.1, 311.7));
  p += dot(p, p + 74.39);
  return fract(p.x * p.y);
}

// Returns nearest hit distance along the ray, or -1.0 on miss.
// Derivation: substitute P = ro + t*rd into |P|² = 1, solve quadratic.
float hitUnitSphere(vec3 ro, vec3 rd) {
  float b = dot(ro, rd);
  float c = dot(ro, ro) - 1.0;
  float disc = b * b - c;
  if (disc < 0.0) return -1.0;
  return -b - sqrt(disc);
}

float oppositionSurge(float cosPhase) {
  // Hapke opposition surge
  // full moon is cosPhase == 1
  // h  = width of spike (~0.05 is narrow/realistic for lunar soil)
  // B0 = peak magnitude above baseline
  float h = 0.1;
  float B0 = 0.15;
  float tanHalfG = sqrt((1.0 - cosPhase) / max(1.0 + cosPhase, 1e-4));
  float surge = max(B0 / (1.0 + tanHalfG / h), 0.0);

  return surge;
}

float starField(vec3 rd, float time) {
  // Rotate star field leftward in sync with sun
  vec3 dir = rotateY(rd, -time);
  float u = 0.5 + atan(dir.z, dir.x) / (2.0 * PI);
  float v = 0.5 + asin(clamp(dir.y, -1.0, 1.0)) / PI;
  vec2 uv = vec2(u, v);

  float stars = 0.0;

  // Layer 1: sparse bright stars
  vec2 cell = floor(uv * 50.0);
  vec2 cellUV = fract(uv * 50.0);
  if (hash(cell) > 0.95) {
    vec2 pos = vec2(hash(cell + 3.7), hash(cell + 7.1));
    float d = length(cellUV - pos);
    stars += smoothstep(0.02, 0.0, d) * hash(cell + 11.3);
  }

  // Layer 2: dense dim stars
  cell = floor(uv * 200.0);
  cellUV = fract(uv * 200.0);
  if (hash(cell) > 0.80) {
    vec2 pos = vec2(hash(cell + 5.2), hash(cell + 9.4));
    float d = length(cellUV - pos);
    stars += smoothstep(0.04, 0.0, d) * hash(cell + 17.8) * 0.4;
  }

  return stars;
}

void main() {
  // Center UVs and correct for screen aspect ratio
  vec2 ndc = (uv - 0.5) * (iResolution.xy / iResolution.y);

  float time = iTime * SUN_ROTATION;

  vec3 cameraDir = vec3(0.0, 0.0, 1.0);

  vec3 sunDir = rotateY(cameraDir, time);
  float cosPhase = dot(sunDir, cameraDir);

  vec3 cameraPos;
  if (DISTANCE) {
    // Perspective camera looking toward -Z
    float distanceMultiplier = (0.5 + 0.5 * cos(time * 1.072)) * (1.0 - APOGEE / PERIGEE);
    float cameraDistance = CAMERA_DISTANCE * (1.0 + distanceMultiplier);
    cameraPos = cameraDir * cameraDistance;
  } else {
    cameraPos = cameraDir * CAMERA_DISTANCE;
  }
  vec3 rayDirection = normalize(vec3(ndc, -1.0));

  float hitDistance = hitUnitSphere(cameraPos, rayDirection);
  if (hitDistance < 0.0) {
    if (STARS) {
      gl_FragColor = vec4(vec3(starField(rayDirection, time)), 1.0);
    } else {
      gl_FragColor = vec4(0.0, 0.0, 0.0, 1.0); // black space background
    }
    return;
  }

  vec3 pos = cameraPos + hitDistance * rayDirection; // point on unit sphere surface
  vec3 normal = normalize(pos); // normal == position for a unit sphere

  vec3 libPos;
  if (LIBRATION) {
    // Equirectangular (lat/lon) UV mapping, with lunar libration
    float libLon = radians(7.9) * sin(time * 1.072); // east/west
    float libLat = radians(6.7) * sin(time * 1.085); // north/south
    libPos = rotateX(rotateY(pos, libLon), libLat);
  } else {
    libPos = pos;
  }
  vec2 texUV = vec2(
      0.5 + atan(libPos.z, libPos.x) / (2.0 * PI),
      0.5 + asin(clamp(libPos.y, -1.0, 1.0)) / PI
    );

  // moon surface texture lookup
  vec3 moonColor = texture2D(moon, texUV).rgb;

  // Sun + matte surface + tiny ambient so the dark side isn't pitch black
  float NdotSun = max(dot(normal, sunDir), 0.0);
  float NdotCam = max(dot(normal, cameraDir), 0.0);

  float matte = NdotSun / (NdotSun + NdotCam + 1e-4) * 2.0;
  float surge = SURGE ? oppositionSurge(cosPhase) : 0.0;

  gl_FragColor = vec4(moonColor * (AMBIENT + matte + surge), 1.0);

  // gl_FragColor.rgb = pow(gl_FragColor.rgb, vec3(0.8));

  if (ANTIALIAS) {
    // Blend black the edge of the sphere
    gl_FragColor.rgb *= smoothstep(0.2, 0.3, NdotCam);
  }
}
