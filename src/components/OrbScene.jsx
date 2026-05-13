import { useEffect, useRef } from 'react';
import * as THREE from 'three';

/**
 * Marketing-site variant of the app's OrbScene.
 *
 * Same shaders, same emotion/breath system as the real orb — but:
 *   - mic-level IPC removed (no Electron on the website)
 *   - socket ambient cues removed (no backend on the website)
 *   - GIF/PNG export helpers removed (dev-only tools)
 *
 * Source of truth: Ame/src/components/OrbScene.jsx
 */

// ── Glossy sphere shaders ────────────────────────────────────
const glossVert = /* glsl */`
  varying vec3 vNormal;
  varying vec3 vPosition;
  varying vec2 vUv;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vPosition = (modelMatrix * vec4(position, 1.0)).xyz;
    vUv = uv;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;
const glossFrag = /* glsl */`
  uniform vec3 uColorBase;
  uniform float uTime;
  uniform float uBreathPhase;
  uniform float uBreathDepth;
  varying vec3 vNormal;
  varying vec3 vPosition;

  float breathEnvelope(float p) {
    if (p < 0.4) {
      float t = p / 0.4;
      return 1.0 - pow(1.0 - t, 3.0);
    } else {
      float t = (p - 0.4) / 0.6;
      return 1.0 - (t < 0.5 ? 4.0 * t * t * t : 1.0 - pow(-2.0 * t + 2.0, 3.0) / 2.0);
    }
  }

  void main() {
    vec3 viewDir = normalize(cameraPosition - vPosition);
    float fresnel = pow(1.0 - dot(viewDir, vNormal), 2.0);
    float shift = dot(viewDir, vNormal);

    vec3 iridColor2 = uColorBase * 0.2 + vec3(1.0) * 0.8;
    vec3 iridColor3 = vec3(uColorBase.b, uColorBase.r, uColorBase.g);

    vec3 surfaceColor = mix(uColorBase, iridColor2, pow(shift, 2.0));
    surfaceColor = mix(surfaceColor, iridColor3, fresnel * 0.7);

    vec3 lightDir = normalize(vec3(1.5, 2.0, 1.0));
    vec3 halfVec = normalize(lightDir + viewDir);
    float specular = pow(max(dot(vNormal, halfVec), 0.0), 128.0);
    surfaceColor += vec3(specular * 1.5);
    surfaceColor += uColorBase * fresnel * 0.8;

    vec3 reflectDir = reflect(-viewDir, vNormal);
    float envReflect = pow(max(reflectDir.y + 0.5, 0.0), 2.0) * 0.3;
    surfaceColor += vec3(envReflect);

    float env = breathEnvelope(uBreathPhase);
    float pulse = 1.0 + (env - 0.5) * uBreathDepth * 2.0;
    surfaceColor *= pulse;

    gl_FragColor = vec4(surfaceColor, 0.92);
  }
`;

// ── Contour line shaders (Perlin noise) ──────────────────────
const contourVert = /* glsl */`
  varying vec3 vNormal;
  varying vec3 vPosition;
  void main() {
    vNormal = normalize(normalMatrix * normal);
    vPosition = (modelMatrix * vec4(position, 1.0)).xyz;
    gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
  }
`;
const contourFrag = /* glsl */`
  uniform float uTime;
  uniform float uNoiseScale;
  uniform float uLineWidth;
  uniform float uLineCount;
  uniform float uAnimSpeed;
  uniform vec3  uLineColor;
  uniform float uOpacity;

  varying vec3 vNormal;
  varying vec3 vPosition;

  vec3 mod289v3(vec3 x){ return x - floor(x*(1./289.))*289.; }
  vec4 mod289v4(vec4 x){ return x - floor(x*(1./289.))*289.; }
  vec4 permute(vec4 x){ return mod289v4(((x*34.)+1.)*x); }
  vec4 taylorInvSqrt(vec4 r){ return 1.7928429-.8537347*r; }
  vec3 fade(vec3 t){ return t*t*t*(t*(t*6.-15.)+10.); }

  float cnoise(vec3 P){
    vec3 Pi0=floor(P), Pi1=Pi0+vec3(1.);
    Pi0=mod289v3(Pi0); Pi1=mod289v3(Pi1);
    vec3 Pf0=fract(P), Pf1=Pf0-vec3(1.);
    vec4 ix=vec4(Pi0.x,Pi1.x,Pi0.x,Pi1.x);
    vec4 iy=vec4(Pi0.yy,Pi1.yy);
    vec4 iz0=Pi0.zzzz, iz1=Pi1.zzzz;
    vec4 ixy=permute(permute(ix)+iy);
    vec4 ixy0=permute(ixy+iz0), ixy1=permute(ixy+iz1);
    vec4 gx0=ixy0*(1./7.), gy0=fract(floor(gx0)*(1./7.))-.5;
    gx0=fract(gx0);
    vec4 gz0=vec4(.5)-abs(gx0)-abs(gy0);
    vec4 sz0=step(gz0,vec4(0.));
    gx0-=sz0*(step(vec4(0.),gx0)-.5); gy0-=sz0*(step(vec4(0.),gy0)-.5);
    vec4 gx1=ixy1*(1./7.), gy1=fract(floor(gx1)*(1./7.))-.5;
    gx1=fract(gx1);
    vec4 gz1=vec4(.5)-abs(gx1)-abs(gy1);
    vec4 sz1=step(gz1,vec4(0.));
    gx1-=sz1*(step(vec4(0.),gx1)-.5); gy1-=sz1*(step(vec4(0.),gy1)-.5);
    vec3 g000=vec3(gx0.x,gy0.x,gz0.x), g100=vec3(gx0.y,gy0.y,gz0.y);
    vec3 g010=vec3(gx0.z,gy0.z,gz0.z), g110=vec3(gx0.w,gy0.w,gz0.w);
    vec3 g001=vec3(gx1.x,gy1.x,gz1.x), g101=vec3(gx1.y,gy1.y,gz1.y);
    vec3 g011=vec3(gx1.z,gy1.z,gz1.z), g111=vec3(gx1.w,gy1.w,gz1.w);
    vec4 norm0=taylorInvSqrt(vec4(dot(g000,g000),dot(g010,g010),dot(g100,g100),dot(g110,g110)));
    g000*=norm0.x; g010*=norm0.y; g100*=norm0.z; g110*=norm0.w;
    vec4 norm1=taylorInvSqrt(vec4(dot(g001,g001),dot(g011,g011),dot(g101,g101),dot(g111,g111)));
    g001*=norm1.x; g011*=norm1.y; g101*=norm1.z; g111*=norm1.w;
    float n000=dot(g000,Pf0);
    float n100=dot(g100,vec3(Pf1.x,Pf0.yz));
    float n010=dot(g010,vec3(Pf0.x,Pf1.y,Pf0.z));
    float n110=dot(g110,vec3(Pf1.xy,Pf0.z));
    float n001=dot(g001,vec3(Pf0.xy,Pf1.z));
    float n101=dot(g101,vec3(Pf1.x,Pf0.y,Pf1.z));
    float n011=dot(g011,vec3(Pf0.x,Pf1.yz));
    float n111=dot(g111,Pf1);
    vec3 fade_xyz=fade(Pf0);
    vec4 nz=mix(vec4(n000,n100,n010,n110),vec4(n001,n101,n011,n111),fade_xyz.z);
    vec2 nyz=mix(nz.xy,nz.zw,fade_xyz.y);
    return 2.2*mix(nyz.x,nyz.y,fade_xyz.x);
  }

  void main() {
    float wave1 = sin(vPosition.y * 8.0 + uTime * uAnimSpeed * 0.2);
    float wave2 = sin((vPosition.x + vPosition.z) * 6.0 + uTime * uAnimSpeed * 0.15);
    float wave3 = cnoise(vPosition * 1.5 + vec3(uTime * uAnimSpeed * 0.1));
    float combined = wave1 * 0.4 + wave2 * 0.3 + wave3 * 0.3;

    float contour = fract(combined * uLineCount);
    float line = 1.0 - smoothstep(0.0, uLineWidth, min(contour, 1.0 - contour));

    if (line < 0.01) discard;

    vec3 viewDir = normalize(cameraPosition - vPosition);
    float fresnel = pow(1.0 - dot(viewDir, vNormal), 1.5);
    float brightness = 0.6 + fresnel * 0.4;

    gl_FragColor = vec4(uLineColor * brightness, line * uOpacity);
  }
`;

const CONTOUR_CFG = {
  idle:      { uNoiseScale: 1.8, uLineWidth: 0.08, uLineCount: 5.0, uAnimSpeed: 0.3, uOpacity: 0.85 },
  listening: { uNoiseScale: 2.0, uLineWidth: 0.08, uLineCount: 5.0, uAnimSpeed: 0.5, uOpacity: 0.85 },
  thinking:  { uNoiseScale: 2.5, uLineWidth: 0.06, uLineCount: 5.0, uAnimSpeed: 1.2, uOpacity: 0.85 },
  speaking:  { uNoiseScale: 2.2, uLineWidth: 0.08, uLineCount: 5.0, uAnimSpeed: 0.9, uOpacity: 0.85 },
};

const EMOTION_CFG = {
  watching:  { opacityMul: 0.85, speedMul: 1.00, particleOpacityMul: 0.85, breathRate: 1.0,  breathDepth: 0.05 },
  curious:   { opacityMul: 1.05, speedMul: 1.80, particleOpacityMul: 1.10, breathRate: 1.6,  breathDepth: 0.04 },
  holding:   { opacityMul: 0.92, speedMul: 0.60, particleOpacityMul: 0.80, breathRate: 0.55, breathDepth: 0.07 },
  excited:   { opacityMul: 1.10, speedMul: 2.20, particleOpacityMul: 1.20, breathRate: 2.0,  breathDepth: 0.06 },
  withdrawn: { opacityMul: 0.55, speedMul: 0.50, particleOpacityMul: 0.50, breathRate: 0.3,  breathDepth: 0.03 },
  listening: { opacityMul: 1.00, speedMul: 1.10, particleOpacityMul: 1.00, breathRate: 1.2,  breathDepth: 0.05 },
  thinking:  { opacityMul: 0.80, speedMul: 0.25, particleOpacityMul: 0.75, breathRate: 0.2,  breathDepth: 0.08 },
};
const EMOTION_DEFAULT = EMOTION_CFG.watching;

export default function OrbScene({
  state       = 'idle',
  size        = 560,
  accentColor = '#6c63ff',
  emotion     = 'watching',
}) {
  const mountRef       = useRef(null);
  const rendererRef    = useRef(null);
  const sceneRef       = useRef(null);
  const cameraRef      = useRef(null);
  const stateRef       = useRef(state);
  const accentColorRef = useRef(accentColor || '#6c63ff');
  const emotionRef     = useRef(emotion);

  useEffect(() => { stateRef.current       = state; }, [state]);
  useEffect(() => { accentColorRef.current = accentColor || '#6c63ff'; }, [accentColor]);
  useEffect(() => { emotionRef.current     = emotion; }, [emotion]);

  useEffect(() => {
    const mount = mountRef.current;
    if (!mount) return;

    const W = size, H = size;

    let renderer;
    try {
      renderer = new THREE.WebGLRenderer({
        antialias: true,
        alpha: true,
        powerPreference: 'high-performance',
      });
    } catch (e) {
      console.error('WebGL init failed', e);
      return;
    }
    renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    renderer.setSize(W, H);
    renderer.setClearColor(0x000000, 0);
    renderer.toneMapping = THREE.ACESFilmicToneMapping;
    renderer.toneMappingExposure = 1.2;
    renderer.domElement.style.width = '100%';
    renderer.domElement.style.height = '100%';
    renderer.domElement.style.display = 'block';
    mount.appendChild(renderer.domElement);

    const scene  = new THREE.Scene();
    const camera = new THREE.PerspectiveCamera(50, W / H, 0.1, 100);
    camera.position.set(0, 0, 3.2);

    rendererRef.current = renderer;
    sceneRef.current    = scene;
    cameraRef.current   = camera;

    scene.add(new THREE.AmbientLight(0x111111, 1.0));
    const pLight = new THREE.PointLight(new THREE.Color(accentColorRef.current), 2.0, 10);
    pLight.position.set(2, 2, 2);
    scene.add(pLight);

    // Layer 1 — glossy sphere
    const glossMat = new THREE.ShaderMaterial({
      vertexShader: glossVert,
      fragmentShader: glossFrag,
      uniforms: {
        uColorBase:    { value: new THREE.Color(accentColorRef.current) },
        uTime:         { value: 0 },
        uBreathPhase:  { value: 0 },
        uBreathDepth:  { value: 0.05 },
      },
      transparent: true,
      depthWrite: false,
    });
    const glossMesh = new THREE.Mesh(new THREE.SphereGeometry(1.0, 128, 128), glossMat);
    scene.add(glossMesh);

    // Layer 2 — contour lines
    const contourMat = new THREE.ShaderMaterial({
      vertexShader: contourVert,
      fragmentShader: contourFrag,
      uniforms: {
        uTime:       { value: 0 },
        uNoiseScale: { value: 1.8 },
        uLineWidth:  { value: 0.04 },
        uLineCount:  { value: 6.0 },
        uAnimSpeed:  { value: 0.3 },
        uLineColor:  { value: new THREE.Color(accentColorRef.current) },
        uOpacity:    { value: 0.5 },
      },
      transparent: true,
      depthWrite: false,
      side: THREE.FrontSide,
    });
    const contourMesh = new THREE.Mesh(new THREE.SphereGeometry(1.002, 128, 128), contourMat);
    scene.add(contourMesh);

    // Layer 4A — close orbital particles
    const ORB_A = 50;
    const orbAData = Array.from({ length: ORB_A }, () => ({
      radius: 1.6 + Math.random() * 0.4,
      speed:  0.2 + Math.random() * 0.6,
      offset: Math.random() * Math.PI * 2,
      tilt:   (Math.random() - 0.5) * Math.PI,
    }));
    const orbAPos = new Float32Array(ORB_A * 3);
    const orbAGeo = new THREE.BufferGeometry();
    orbAGeo.setAttribute('position', new THREE.BufferAttribute(orbAPos, 3));
    const orbAMat = new THREE.PointsMaterial({
      color: new THREE.Color(accentColorRef.current),
      size: 0.018, transparent: true, opacity: 0.7,
      sizeAttenuation: true, depthWrite: false,
    });
    scene.add(new THREE.Points(orbAGeo, orbAMat));

    // Layer 4B — distant ambient particles
    const ORB_B = 30;
    const orbBPos = new Float32Array(ORB_B * 3);
    const orbBVel = new Float32Array(ORB_B * 3);
    for (let i = 0; i < ORB_B; i++) {
      const r = 2.5 + Math.random() * 1.0;
      const th = Math.random() * Math.PI * 2;
      const ph = Math.acos(2 * Math.random() - 1);
      orbBPos[i*3]   = r * Math.sin(ph) * Math.cos(th);
      orbBPos[i*3+1] = r * Math.sin(ph) * Math.sin(th);
      orbBPos[i*3+2] = r * Math.cos(ph);
      orbBVel[i*3]   = (Math.random() - 0.5) * 0.001;
      orbBVel[i*3+1] = (Math.random() - 0.5) * 0.001;
      orbBVel[i*3+2] = (Math.random() - 0.5) * 0.001;
    }
    const orbBGeo = new THREE.BufferGeometry();
    orbBGeo.setAttribute('position', new THREE.BufferAttribute(orbBPos, 3));
    const orbBMat = new THREE.PointsMaterial({
      color: new THREE.Color(accentColorRef.current),
      size: 0.008, transparent: true, opacity: 0.3,
      sizeAttenuation: true, depthWrite: false,
    });
    scene.add(new THREE.Points(orbBGeo, orbBMat));

    let shootTimer = 0;
    let shootIdx   = -1;
    let shootPhase = 0;
    const origARadius = orbAData.map(d => d.radius);

    // Resize observer — match wrapper size
    const ro = new ResizeObserver((entries) => {
      for (const e of entries) {
        const w = Math.max(1, Math.round(e.contentRect.width));
        const h = Math.max(1, Math.round(e.contentRect.height));
        renderer.setSize(w, h, false);
        camera.aspect = w / h;
        camera.updateProjectionMatrix();
      }
    });
    ro.observe(mount);

    // Pause animation when offscreen — saves battery on long scroll pages
    let visible = true;
    const vo = new IntersectionObserver(([entry]) => { visible = entry.isIntersecting; });
    vo.observe(mount);

    let t = 0;
    let raf;
    let breathPhase = 0;
    let breathDepth = 0.05;
    const BREATH_BASE_SEC = 4.0;

    function animate() {
      raf = requestAnimationFrame(animate);
      if (!visible) return;

      const frameDt = 0.016;
      t += frameDt;

      const st  = stateRef.current;
      const ac  = accentColorRef.current;
      const isThinking = st === 'thinking';
      const isSpeaking = st === 'speaking';
      const isListening = st === 'listening';

      const acColor     = isThinking ? new THREE.Color('#fbbf24') : new THREE.Color(ac);
      const acColorBase = isThinking ? new THREE.Color('#3e2a00') : new THREE.Color(ac);

      glossMat.uniforms.uColorBase.value.copy(acColorBase);
      contourMat.uniforms.uLineColor.value.copy(acColor);
      orbAMat.color.copy(acColor);
      orbBMat.color.copy(acColor);
      pLight.color.copy(acColor);

      glossMat.uniforms.uTime.value  = t;
      contourMat.uniforms.uTime.value = t;

      const emoCfg = EMOTION_CFG[emotionRef.current] || EMOTION_DEFAULT;

      // Breath system
      const targetRate  = emoCfg.breathRate;
      const targetDepth = emoCfg.breathDepth;
      breathDepth += (targetDepth - breathDepth) * 0.08;
      const cycleSec = BREATH_BASE_SEC / Math.max(0.05, targetRate);
      breathPhase = (breathPhase + frameDt / cycleSec) % 1.0;
      glossMat.uniforms.uBreathPhase.value = breathPhase;
      glossMat.uniforms.uBreathDepth.value = breathDepth;

      // Contour lerp toward state target
      const cfg = CONTOUR_CFG[st] || CONTOUR_CFG.idle;
      const cu  = contourMat.uniforms;
      const lerpSpeed = 0.05;
      const opacityTarget = cfg.uOpacity * emoCfg.opacityMul;
      const speedTarget   = cfg.uAnimSpeed * emoCfg.speedMul;
      cu.uNoiseScale.value += (cfg.uNoiseScale - cu.uNoiseScale.value) * lerpSpeed;
      cu.uLineWidth.value  += (cfg.uLineWidth  - cu.uLineWidth.value)  * lerpSpeed;
      cu.uLineCount.value  += (cfg.uLineCount  - cu.uLineCount.value)  * lerpSpeed;
      cu.uAnimSpeed.value  += (speedTarget     - cu.uAnimSpeed.value)  * lerpSpeed;
      cu.uOpacity.value    += (opacityTarget   - cu.uOpacity.value)    * lerpSpeed;

      orbAMat.opacity += (0.7 * emoCfg.particleOpacityMul - orbAMat.opacity) * lerpSpeed;
      orbBMat.opacity += (0.3 * emoCfg.particleOpacityMul - orbBMat.opacity) * lerpSpeed;

      // Orbital particles A
      const speedMult  = (isSpeaking ? 1.8 : isListening ? 1.3 : isThinking ? 0.7 : 1.0) * emoCfg.speedMul;
      const radiusMult = isListening ? 0.9 : isThinking  ? 0.5 : 1.0;

      if (isSpeaking) {
        shootTimer += frameDt;
        if (shootTimer > 0.5) {
          shootTimer = 0;
          shootIdx   = Math.floor(Math.random() * ORB_A);
          shootPhase = 1;
        }
      } else {
        shootIdx = -1;
        shootPhase = 0;
      }

      for (let i = 0; i < ORB_A; i++) {
        const d     = orbAData[i];
        const angle = d.speed * speedMult * t + d.offset;
        let r = d.radius * radiusMult;

        if (i === shootIdx) {
          if (shootPhase === 1) {
            r = origARadius[i] + (3.0 - origARadius[i]) * Math.min(shootTimer * 4, 1);
            if (shootTimer * 4 >= 1) shootPhase = 2;
          } else if (shootPhase === 2) {
            r = 3.0 + (origARadius[i] - 3.0) * Math.min((shootTimer - 0.25) * 4, 1);
          }
        }

        if (isThinking) {
          const collapse = 0.25 + Math.sin(t * 2 + i) * 0.1;
          orbAPos[i*3]   = Math.cos(angle) * r * collapse * Math.cos(d.tilt);
          orbAPos[i*3+1] = Math.sin(angle * 0.7) * r * collapse * 0.4;
          orbAPos[i*3+2] = Math.sin(angle) * r * collapse * Math.sin(d.tilt);
        } else {
          orbAPos[i*3]   = Math.cos(angle) * r * Math.cos(d.tilt);
          orbAPos[i*3+1] = Math.sin(angle * 0.7) * r * 0.4;
          orbAPos[i*3+2] = Math.sin(angle) * r * Math.sin(d.tilt);
        }
      }
      orbAGeo.attributes.position.needsUpdate = true;

      for (let i = 0; i < ORB_B; i++) {
        orbBPos[i*3]   += orbBVel[i*3];
        orbBPos[i*3+1] += orbBVel[i*3+1];
        orbBPos[i*3+2] += orbBVel[i*3+2];
        const dx = orbBPos[i*3], dy = orbBPos[i*3+1], dz = orbBPos[i*3+2];
        const dist = Math.sqrt(dx*dx + dy*dy + dz*dz);
        if (dist > 3.5 || dist < 2.3) {
          orbBVel[i*3] *= -1; orbBVel[i*3+1] *= -1; orbBVel[i*3+2] *= -1;
        }
      }
      orbBGeo.attributes.position.needsUpdate = true;

      glossMesh.rotation.y   = t * 0.05;
      contourMesh.rotation.y = t * 0.05;

      renderer.render(scene, camera);
    }

    animate();

    return () => {
      cancelAnimationFrame(raf);
      ro.disconnect();
      vo.disconnect();
      glossMat.dispose();
      contourMat.dispose();
      orbAMat.dispose();
      orbBMat.dispose();
      orbAGeo.dispose();
      orbBGeo.dispose();
      renderer.dispose();
      if (mount.contains(renderer.domElement)) mount.removeChild(renderer.domElement);
    };
  }, [size]);

  return (
    <div ref={mountRef} style={{ width: '100%', height: '100%', display: 'block' }} />
  );
}
