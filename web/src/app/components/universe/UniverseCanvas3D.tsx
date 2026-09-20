"use client";

import React, { useRef, useMemo, useEffect, useState, useCallback } from "react";
import * as THREE from "three";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls } from "@react-three/drei";
import { UniverseData, REGION_PALETTE_HEX, hexToRgb01, QualityTier } from "./types";

type OrbitControlsImpl = any;

interface UniverseCanvas3DProps {
  data: UniverseData;
  tier: QualityTier;
  focusedRegionId: number | null;
  focusedTrackId: string | null;
  blindspotRegionId: number | null;
  recommendationCoords?: Array<[number, number, number]>;
  onSelectTrack: (trackId: string) => void;
  onFpsReport?: (fps: number) => void;
  onTierChange?: (newTier: QualityTier) => void;
}

// Generates a smooth soft-circle glow sprite texture
function createCircleTexture(): THREE.Texture {
  const canvas = document.createElement("canvas");
  canvas.width = 64;
  canvas.height = 64;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    const gradient = ctx.createRadialGradient(32, 32, 0, 32, 32, 32);
    gradient.addColorStop(0, "rgba(255,255,255,1)");
    gradient.addColorStop(0.35, "rgba(255,255,255,0.75)");
    gradient.addColorStop(0.7, "rgba(255,255,255,0.15)");
    gradient.addColorStop(1, "rgba(255,255,255,0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 64, 64);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

// 1. Starfield Point Cloud Component
function Starfield({
  data,
  tier,
  focusedRegionId,
  onHoverTrack,
  onClickTrack,
}: {
  data: UniverseData;
  tier: QualityTier;
  focusedRegionId: number | null;
  onHoverTrack: (info: { trackIdx: number; regId: number; pos: [number, number, number] } | null) => void;
  onClickTrack: (trackIdx: number) => void;
}) {
  const pointsRef = useRef<THREE.Points | null>(null);
  const { raycaster, mouse, camera } = useThree();

  const circleTexture = useMemo(() => createCircleTexture(), []);

  // Determine sampling stride based on tier budget (Desktop high: 15k, mid: 8k, mobile: 4k)
  const maxPoints = tier === "high" ? 15000 : tier === "mid" ? 8000 : 4000;

  const { geometry, trackIndices, positionsArray } = useMemo(() => {
    const raw = data.points_quantized;
    const stride = 5;
    const totalCount = Math.floor(raw.length / stride);
    const step = Math.max(1, Math.floor(totalCount / maxPoints));

    const selectedCount = Math.ceil(totalCount / step);
    const positions = new Float32Array(selectedCount * 3);
    const colors = new Float32Array(selectedCount * 3);
    const tIndices = new Int32Array(selectedCount);

    let pIdx = 0;
    for (let i = 0; i < totalCount; i += step) {
      const idx = i * stride;
      const x = raw[idx] / 32767.0;
      const y = raw[idx + 1] / 32767.0;
      const z = raw[idx + 2] / 32767.0;
      const reg = raw[idx + 3];
      const trk = raw[idx + 4];

      positions[pIdx * 3] = x;
      positions[pIdx * 3 + 1] = y;
      positions[pIdx * 3 + 2] = z;

      const rgb = hexToRgb01(REGION_PALETTE_HEX[reg % REGION_PALETTE_HEX.length]);
      const isFocused = focusedRegionId === null || reg === focusedRegionId;

      if (isFocused) {
        colors[pIdx * 3] = rgb[0];
        colors[pIdx * 3 + 1] = rgb[1];
        colors[pIdx * 3 + 2] = rgb[2];
      } else {
        // Dim unselected regions
        colors[pIdx * 3] = rgb[0] * 0.2;
        colors[pIdx * 3 + 1] = rgb[1] * 0.2;
        colors[pIdx * 3 + 2] = rgb[2] * 0.2;
      }

      tIndices[pIdx] = trk;
      pIdx++;
    }

    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.BufferAttribute(positions.subarray(0, pIdx * 3), 3));
    geom.setAttribute("color", new THREE.BufferAttribute(colors.subarray(0, pIdx * 3), 3));

    return {
      geometry: geom,
      trackIndices: tIndices.subarray(0, pIdx),
      positionsArray: positions.subarray(0, pIdx * 3),
    };
  }, [data.points_quantized, maxPoints, focusedRegionId]);

  // Raycasting for point hover and click
  useFrame(() => {
    if (!pointsRef.current) return;
    raycaster.params.Points = { threshold: 0.035 };
    const intersects = raycaster.intersectObject(pointsRef.current);

    if (intersects.length > 0) {
      const hit = intersects[0];
      const index = hit.index;
      if (index !== undefined && index < trackIndices.length) {
        const trk = trackIndices[index];
        const reg = data.points_quantized[index * 5 + 3] ?? 0;
        const pos: [number, number, number] = [
          positionsArray[index * 3],
          positionsArray[index * 3 + 1],
          positionsArray[index * 3 + 2],
        ];
        onHoverTrack({ trackIdx: trk, regId: reg, pos });
        return;
      }
    }
    onHoverTrack(null);
  });

  // Cleanup
  useEffect(() => {
    return () => {
      geometry.dispose();
      circleTexture.dispose();
    };
  }, [geometry, circleTexture]);

  return (
    <points
      ref={pointsRef}
      geometry={geometry}
      onClick={(e) => {
        e.stopPropagation();
        if (e.index !== undefined && e.index < trackIndices.length) {
          onClickTrack(trackIndices[e.index]);
        }
      }}
    >
      <pointsMaterial
        size={tier === "high" ? 0.024 : 0.03}
        map={circleTexture}
        vertexColors
        transparent
        alphaTest={0.01}
        opacity={0.88}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        sizeAttenuation
      />
    </points>
  );
}

// 2. Glowing Taste Beacon & Recommendation Path Arcs
function DynamicBeacons({
  recommendationCoords,
  blindspotCentroid,
}: {
  recommendationCoords?: Array<[number, number, number]>;
  blindspotCentroid?: [number, number, number] | null;
}) {
  const haloRef = useRef<THREE.Mesh | null>(null);

  useFrame(({ clock }) => {
    const t = clock.getElapsedTime();
    if (haloRef.current) {
      const s = 1.0 + 0.15 * Math.sin(t * 2.5);
      haloRef.current.scale.set(s, s, s);
      haloRef.current.rotation.z = t * 0.4;
    }
  });

  // Recommendation path curve
  const pathLineMesh = useMemo(() => {
    if (!recommendationCoords || recommendationCoords.length < 2) return null;
    const points = recommendationCoords.map((c) => new THREE.Vector3(c[0], c[1], c[2]));
    const curve = new THREE.CatmullRomCurve3(points);
    const curvePoints = curve.getPoints(Math.min(100, recommendationCoords.length * 5));
    const geom = new THREE.BufferGeometry().setFromPoints(curvePoints);
    const mat = new THREE.LineBasicMaterial({
      color: "#d4af37",
      transparent: true,
      opacity: 0.65,
    });
    return new THREE.Line(geom, mat);
  }, [recommendationCoords]);

  return (
    <group>
      {/* Recommendation Journey Arc */}
      {pathLineMesh && <primitive object={pathLineMesh} />}

      {/* Recommendation Nodes */}
      {recommendationCoords?.map((c, i) => (
        <mesh key={i} position={[c[0], c[1], c[2]]}>
          <sphereGeometry args={[0.016, 12, 12]} />
          <meshBasicMaterial color={i === 0 ? "#10b981" : "#d4af37"} />
        </mesh>
      ))}

      {/* Blindspot Halo Beacon */}
      {blindspotCentroid && (
        <group position={[blindspotCentroid[0], blindspotCentroid[1], blindspotCentroid[2]]}>
          <mesh ref={haloRef}>
            <ringGeometry args={[0.08, 0.10, 32]} />
            <meshBasicMaterial color="#38bdf8" side={THREE.DoubleSide} transparent opacity={0.7} />
          </mesh>
          <pointLight color="#38bdf8" intensity={1.5} distance={0.5} />
        </group>
      )}
    </group>
  );
}

// 3. Camera Fly-Through & Target Tracking Controller
function CameraController({
  targetPos,
  controlsRef,
}: {
  targetPos: [number, number, number] | null;
  controlsRef: React.RefObject<OrbitControlsImpl>;
}) {
  const { camera } = useThree();

  useFrame(() => {
    if (!targetPos || !controlsRef.current) return;

    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const targetVec = new THREE.Vector3(targetPos[0], targetPos[1], targetPos[2]);

    if (prefersReducedMotion) {
      // Instant camera cut
      controlsRef.current.target.copy(targetVec);
      controlsRef.current.update();
    } else {
      // Smooth lerp
      controlsRef.current.target.lerp(targetVec, 0.05);
      controlsRef.current.update();
    }
  });

  return null;
}

// 4. Performance Tier FPS Monitor
function FpsMonitor({
  onFpsReport,
  onTierChange,
  currentTier,
}: {
  onFpsReport?: (fps: number) => void;
  onTierChange?: (newTier: QualityTier) => void;
  currentTier: QualityTier;
}) {
  const frameCount = useRef(0);
  const lastTime = useRef(performance.now());
  const lowFpsCount = useRef(0);

  useFrame(() => {
    frameCount.current++;
    const now = performance.now();
    const elapsed = now - lastTime.current;

    if (elapsed >= 1000) {
      const fps = Math.round((frameCount.current * 1000) / elapsed);
      onFpsReport?.(fps);

      // Auto-quality drop check: if FPS < 30 for 3 consecutive seconds, drop tier
      if (fps < 30) {
        lowFpsCount.current++;
        if (lowFpsCount.current >= 3) {
          if (currentTier === "high") onTierChange?.("mid");
          else if (currentTier === "mid") onTierChange?.("mobile");
          lowFpsCount.current = 0;
        }
      } else {
        lowFpsCount.current = Math.max(0, lowFpsCount.current - 1);
      }

      frameCount.current = 0;
      lastTime.current = now;
    }
  });

  return null;
}

// Primary 3D Canvas Export Component
export function UniverseCanvas3D({
  data,
  tier,
  focusedRegionId,
  focusedTrackId,
  blindspotRegionId,
  recommendationCoords,
  onSelectTrack,
  onFpsReport,
  onTierChange,
}: UniverseCanvas3DProps) {
  const controlsRef = useRef<OrbitControlsImpl | null>(null);
  const [hoveredTrack, setHoveredTrack] = useState<{
    trackIdx: number;
    regId: number;
    pos: [number, number, number];
  } | null>(null);

  // Target camera focus position
  const targetPos = useMemo<[number, number, number] | null>(() => {
    if (focusedRegionId !== null) {
      const reg = data.regions.find((r) => r.region_id === focusedRegionId);
      if (reg) return reg.centroid_3d;
    }
    return null;
  }, [focusedRegionId, data.regions]);

  const blindspotCentroid = useMemo<[number, number, number] | null>(() => {
    if (blindspotRegionId !== null) {
      const reg = data.regions.find((r) => r.region_id === blindspotRegionId);
      if (reg) return reg.centroid_3d;
    }
    return null;
  }, [blindspotRegionId, data.regions]);

  return (
    <div className="relative w-full h-full bg-[#0a0c13] select-none">
      <Canvas
        camera={{ position: [0, 0, 2.2], fov: 60, near: 0.01, far: 50 }}
        gl={{ antialias: true, alpha: false, powerPreference: "high-performance" }}
        dpr={tier === "mobile" ? 1.0 : [1, 2]}
      >
        <ambientLight intensity={0.6} />
        <pointLight position={[5, 5, 5]} intensity={0.8} />

        <OrbitControls
          ref={controlsRef}
          enableDamping
          dampingFactor={0.06}
          rotateSpeed={0.8}
          zoomSpeed={1.1}
          minDistance={0.2}
          maxDistance={5.0}
        />

        <Starfield
          data={data}
          tier={tier}
          focusedRegionId={focusedRegionId}
          onHoverTrack={setHoveredTrack}
          onClickTrack={(trk) => onSelectTrack(`trk_${trk}`)}
        />

        <DynamicBeacons
          recommendationCoords={recommendationCoords}
          blindspotCentroid={blindspotCentroid}
        />

        <CameraController targetPos={targetPos} controlsRef={controlsRef} />

        <FpsMonitor
          onFpsReport={onFpsReport}
          onTierChange={onTierChange}
          currentTier={tier}
        />
      </Canvas>

      {/* Floating Hover Card */}
      {hoveredTrack && (
        <div className="pointer-events-none absolute bottom-5 left-1/2 -translate-x-1/2 z-20 px-4 py-2 rounded-xl bg-[#141924]/90 border border-[#d4af37]/60 text-xs text-[#f1f3f7] shadow-2xl backdrop-blur-md flex items-center gap-3 animate-in fade-in duration-150">
          <span
            className="w-3 h-3 rounded-full"
            style={{
              backgroundColor:
                REGION_PALETTE_HEX[hoveredTrack.regId % REGION_PALETTE_HEX.length],
            }}
          />
          <div>
            <p className="font-bold text-[#f1f3f7]">Track #{hoveredTrack.trackIdx}</p>
            <p className="text-[10px] text-[#8c96a8]">
              Region {hoveredTrack.regId}:{" "}
              {data.regions[hoveredTrack.regId]?.name || "Catalog Zone"}
            </p>
          </div>
          <span className="text-[10px] text-[#d4af37] font-mono pl-2 border-l border-[#242d3e]">
            Click to inspect
          </span>
        </div>
      )}
    </div>
  );
}
