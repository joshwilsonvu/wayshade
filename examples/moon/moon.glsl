// controls
#define DISTANCE true
#define STARS true
#define LIBRATION true
#define TEXTURE true
#define SURFACE false
#define SURGE true
#define ANTIALIAS false

// constants
#define SUN_ROTATION 0.03
#define MOUSE_ROTATION 0.04
#define CAMERA_DISTANCE 2.8
#define AMBIENT 0.02
#define PERIGEE 362600.0
#define APOGEE 405400.0
#define HASHSCALE1 .1031
#define HASHSCALE3 vec3(.1031, .1030, .0973)
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
float hash13(vec3 p3)
{
  p3 = fract(p3 * HASHSCALE1);
  p3 += dot(p3, p3.yzx + 19.19);
  return fract((p3.x + p3.y) * p3.z);
}
vec3 hash33(vec3 p) {
  p = fract(p * HASHSCALE3);
  p += dot(p, p.yxz + 19.19);
  return fract((p.xxy + p.yxx) * p.zyx);
}

float Noise(in vec3 p)
{
  vec3 i = floor(p);
  vec3 f = fract(p);
  f *= f * (3.0 - 2.0 * f);

  return mix(
    mix(mix(hash13(i + vec3(0., 0., 0.)), hash13(i + vec3(1., 0., 0.)), f.x),
      mix(hash13(i + vec3(0., 1., 0.)), hash13(i + vec3(1., 1., 0.)), f.x),
      f.y),
    mix(mix(hash13(i + vec3(0., 0., 1.)), hash13(i + vec3(1., 0., 1.)), f.x),
      mix(hash13(i + vec3(0., 1., 1.)), hash13(i + vec3(1., 1., 1.)), f.x),
      f.y),
    f.z);
}
const mat3 m = mat3(0.00, 0.80, 0.60,
    -0.80, 0.36, -0.48,
    -0.60, -0.48, 0.64) * 1.7;
float FBM(vec3 p)
{
  float f;

  f = 0.5000 * Noise(p);
  p = m * p;
  f += 0.2500 * Noise(p);
  p = m * p;
  f += 0.1250 * Noise(p);
  p = m * p;
  f += 0.0625 * Noise(p);
  p = m * p;
  f += 0.03125 * Noise(p);
  p = m * p;
  f += 0.015625 * Noise(p);
  return f;
}

// procedural craters based on https://www.shadertoy.com/view/MtjGRD
float craters(vec3 x) {
  vec3 p = floor(x);
  vec3 f = fract(x);
  float va = 0.0;
  float wt = 0.0;
  for (int i = -2; i <= 2; i++)
    for (int j = -2; j <= 2; j++)
      for (int k = -2; k <= 2; k++) {
        vec3 g = vec3(i, j, k);
        vec3 o = 0.8 * hash33(p + g);
        float d = distance(f - g, o);
        float w = exp(-4.0 * d);
        va += w * sin(2.0 * PI * sqrt(d));
        wt += w;
      }
  return abs(va / wt);
}

float moonSurface(vec3 p) {
  float result = 0.0;
  for (int i = 0; i < 5; i++) {
    float freq = 0.6 * pow(2.2, i);
    float c = craters(freq * p);
    float n = 0.4 * exp(-3.0 * c) * FBM(10.0 * p);
    float w = clamp(3.0 * pow(0.4, i), 0.0, 1.0);
    result += w * (c + n);
  }
  return pow(result, 3.0);
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

vec3 starField(vec3 rd, float time) {
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

  return vec3(stars);
}

uniform 

void main() {
  // Normalized device coordinates, centered, aspect-corrected
  vec2 ndc = (fragCoord - 0.5 * iResolution.xy) / iResolution.y;
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
      fragColor = vec4(starField(rayDirection, time), 1.0);
    } else {
      fragColor = vec4(0.0, 0.0, 0.0, 1.0); // black space background
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
  // procedural moon surface instead of texture lookup
  vec3 moonColor;
  if (TEXTURE) {
    // read from iChannel0, a sampler2d, from position `libPos`
    moonColor = texture(iChannel0, texUV).rgb;
  } else if (SURFACE) {
    float surf = moonSurface(libPos);
    moonColor = mix(vec3(0.82, 0.81, 0.8), vec3(0.22, 0.21, 0.2), smoothstep(0., 4., surf));
  } else {
    moonColor = vec3(0.22, 0.21, 0.2);
  }

  // Sun + matte surface + tiny ambient so the dark side isn't pitch black
  float NdotSun = max(dot(normal, sunDir), 0.0);
  float NdotCam = max(dot(normal, cameraDir), 0.0);

  float matte = NdotSun / (NdotSun + NdotCam + 1e-4) * 2.0;
  float surge = SURGE ? oppositionSurge(cosPhase) : 0.0;

  fragColor = vec4(moonColor * (AMBIENT + matte + surge), 1.0);

  fragColor.rgb = pow(fragColor.rgb, vec3(0.8));

  if (ANTIALIAS) {
    // Blend black the edge of the sphere
    fragColor.rgb *= (1.0 - smoothstep(0.95, 1.0, length(normal.xy)));
  }
}
