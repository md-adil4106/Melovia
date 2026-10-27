"use client";

import React, { useRef, useMemo, useEffect, useState } from "react";
import * as THREE from "three";
import { Canvas, useFrame, useThree } from "@react-three/fiber";
import { OrbitControls, Html } from "@react-three/drei";
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
  onSelectRegion?: (regionId: number | null) => void;
  onFpsReport?: (fps: number) => void;
  onTierChange?: (newTier: QualityTier) => void;
  showNebulae?: boolean;
  showLabels?: boolean;
  showConstellations?: boolean;
  autoRotate?: boolean;
}

// 1. Ultra-clean radiant star texture (intense bright nucleus + soft diffraction corona)
function createStarTexture(): THREE.Texture {
  const canvas = document.createElement("canvas");
  canvas.width = 128;
  canvas.height = 128;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    const gradient = ctx.createRadialGradient(64, 64, 0, 64, 64, 64);
    gradient.addColorStop(0, "rgba(255, 255, 255, 1.0)");
    gradient.addColorStop(0.12, "rgba(255, 255, 255, 0.95)");
    gradient.addColorStop(0.25, "rgba(230, 242, 255, 0.70)");
    gradient.addColorStop(0.48, "rgba(180, 210, 255, 0.28)");
    gradient.addColorStop(0.78, "rgba(120, 160, 255, 0.05)");
    gradient.addColorStop(1.0, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 128, 128);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

// 2. Soft volumetric cloud texture for cluster nebulae
function createNebulaTexture(): THREE.Texture {
  const canvas = document.createElement("canvas");
  canvas.width = 256;
  canvas.height = 256;
  const ctx = canvas.getContext("2d");
  if (ctx) {
    const gradient = ctx.createRadialGradient(128, 128, 0, 128, 128, 128);
    gradient.addColorStop(0, "rgba(255, 255, 255, 0.75)");
    gradient.addColorStop(0.22, "rgba(255, 255, 255, 0.48)");
    gradient.addColorStop(0.52, "rgba(255, 255, 255, 0.18)");
    gradient.addColorStop(0.82, "rgba(255, 255, 255, 0.04)");
    gradient.addColorStop(1.0, "rgba(0, 0, 0, 0)");
    ctx.fillStyle = gradient;
    ctx.fillRect(0, 0, 256, 256);
  }
  const texture = new THREE.CanvasTexture(canvas);
  texture.needsUpdate = true;
  return texture;
}

// 3. Ambient Cosmic Dust (Deep-space stellar parallax)
function CosmicDust() {
  const dustRef = useRef<THREE.Points | null>(null);
  const texture = useMemo(() => createStarTexture(), []);

  const { geometry } = useMemo(() => {
    const count = 1200;
    const positions = new Float32Array(count * 3);
    const colors = new Float32Array(count * 3);

    const palette = [
      [0.9, 0.95, 1.0],
      [0.7, 0.85, 1.0],
      [1.0, 0.92, 0.8],
      [0.85, 0.8, 1.0],
    ];

    for (let i = 0; i < count; i++) {
      const r = 2.0 + Math.random() * 3.5;
      const theta = Math.random() * Math.PI * 2;
      const phi = Math.acos(2 * Math.random() - 1);

      positions[i * 3] = r * Math.sin(phi) * Math.cos(theta);
      positions[i * 3 + 1] = r * Math.sin(phi) * Math.sin(theta);
      positions[i * 3 + 2] = r * Math.cos(phi);

      const c = palette[Math.floor(Math.random() * palette.length)];
      colors[i * 3] = c[0];
      colors[i * 3 + 1] = c[1];
      colors[i * 3 + 2] = c[2];
    }

    const geom = new THREE.BufferGeometry();
    geom.setAttribute("position", new THREE.BufferAttribute(positions, 3));
    geom.setAttribute("color", new THREE.BufferAttribute(colors, 3));
    return { geometry: geom };
  }, []);

  useFrame(() => {
    if (dustRef.current) {
      dustRef.current.rotation.y += 0.00015;
      dustRef.current.rotation.x += 0.00008;
    }
  });

  return (
    <points ref={dustRef} geometry={geometry}>
      <pointsMaterial
        size={0.015}
        map={texture}
        vertexColors
        transparent
        opacity={0.4}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        sizeAttenuation
      />
    </points>
  );
}

// 4. Volumetric Region Nebulae (Luminous colored ambient dust clouds per cluster)
function RegionNebulae({
  regions,
  focusedRegionId,
  visible = true,
}: {
  regions: UniverseData["regions"];
  focusedRegionId: number | null;
  visible?: boolean;
}) {
  const groupRef = useRef<THREE.Group | null>(null);
  const nebulaTexture = useMemo(() => createNebulaTexture(), []);

  useFrame(() => {
    if (!groupRef.current || !visible) return;
    const t = performance.now() * 0.001;
    groupRef.current.children.forEach((child, idx) => {
      if (child instanceof THREE.Sprite) {
        const reg = regions[idx];
        const isFocused = focusedRegionId !== null && reg?.region_id === focusedRegionId;
        const pulse = 1.0 + 0.08 * Math.sin(t * 1.8 + idx);
        const baseSize = isFocused ? 0.95 : 0.65;
        child.scale.set(baseSize * pulse, baseSize * pulse, 1.0);
      }
    });
  });

  if (!visible) return null;

  return (
    <group ref={groupRef}>
      {regions.map((reg, idx) => {
        const hex = reg.color || REGION_PALETTE_HEX[reg.region_id % REGION_PALETTE_HEX.length];
        const isFocused = focusedRegionId === null || reg.region_id === focusedRegionId;
        const baseOpacity = focusedRegionId === null ? 0.30 : isFocused ? 0.65 : 0.08;

        return (
          <sprite
            key={`nebula-${reg.region_id ?? idx}`}
            position={new THREE.Vector3(reg.centroid_3d[0], reg.centroid_3d[1], reg.centroid_3d[2])}
            scale={[0.7, 0.7, 1]}
          >
            <spriteMaterial
              map={nebulaTexture}
              color={hex}
              transparent
              opacity={baseOpacity}
              blending={THREE.AdditiveBlending}
              depthWrite={false}
            />
          </sprite>
        );
      })}
    </group>
  );
}

// 5. Floating 3D Region Billboard Labels
function RegionLabels({
  regions,
  focusedRegionId,
  onSelectRegion,
  visible = true,
}: {
  regions: UniverseData["regions"];
  focusedRegionId: number | null;
  onSelectRegion?: (regId: number) => void;
  visible?: boolean;
}) {
  if (!visible) return null;

  return (
    <group>
      {regions.map((reg) => {
        const isFocused = focusedRegionId === reg.region_id;
        const color = reg.color || REGION_PALETTE_HEX[reg.region_id % REGION_PALETTE_HEX.length];

        return (
          <group
            key={`label-${reg.region_id}`}
            position={[reg.centroid_3d[0], reg.centroid_3d[1] + 0.08, reg.centroid_3d[2]]}
          >
            <Html
              distanceFactor={3.6}
              center
              zIndexRange={[10, 0]}
              style={{ pointerEvents: "auto", userSelect: "none" }}
            >
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  onSelectRegion?.(reg.region_id);
                }}
                className={`group flex items-center gap-1.5 px-2.5 py-1 rounded-full border transition-all duration-200 cursor-pointer backdrop-blur-xl whitespace-nowrap shadow-lg ${
                  isFocused
                    ? "bg-[#0b0e17]/95 border-white/40 ring-2 ring-white/20 shadow-[0_0_20px_rgba(255,255,255,0.15)] scale-105"
                    : "bg-[#080b13]/80 hover:bg-[#121624]/90 border-white/15 hover:border-white/30 hover:scale-105"
                }`}
                title={`Focus ${reg.name} (${reg.genre_focus})`}
              >
                <span
                  className="w-2 h-2 rounded-full shrink-0 shadow-sm transition-transform group-hover:scale-125"
                  style={{
                    backgroundColor: color,
                    boxShadow: `0 0 8px ${color}`,
                  }}
                />
                <span className="text-[11px] font-bold tracking-wide uppercase text-white/90 group-hover:text-white">
                  {reg.name}
                </span>
                <span className="text-[9px] font-mono text-white/50 px-1 py-0.2 rounded-md bg-white/[0.08] ml-0.5">
                  {reg.track_count ?? 125}
                </span>
              </button>
            </Html>
          </group>
        );
      })}
    </group>
  );
}

// 6. Holographic Selection Reticle & Constellation Web
function StarSelectionOverlay({
  hoveredPos,
  focusedPos,
  positionsArray,
  trackIndices,
  hoveredIdx,
  visible = true,
}: {
  hoveredPos: [number, number, number] | null;
  focusedPos: [number, number, number] | null;
  positionsArray: Float32Array;
  trackIndices: Int32Array;
  hoveredIdx: number | null;
  visible?: boolean;
}) {
  const ringRef = useRef<THREE.Mesh | null>(null);
  const activePos = hoveredPos || focusedPos;

  useFrame(() => {
    if (ringRef.current) {
      ringRef.current.rotation.z += 0.02;
    }
  });

  const constellationGeom = useMemo(() => {
    if (!visible || !activePos || hoveredIdx === null) return null;
    const origin = new THREE.Vector3(activePos[0], activePos[1], activePos[2]);
    const distances: Array<{ dist: number; vec: THREE.Vector3 }> = [];

    const total = trackIndices.length;
    for (let i = 0; i < total; i++) {
      if (i === hoveredIdx) continue;
      const v = new THREE.Vector3(
        positionsArray[i * 3],
        positionsArray[i * 3 + 1],
        positionsArray[i * 3 + 2]
      );
      const d = origin.distanceTo(v);
      if (d < 0.28) {
        distances.push({ dist: d, vec: v });
      }
    }

    distances.sort((a, b) => a.dist - b.dist);
    const topN = distances.slice(0, 5);
    if (topN.length === 0) return null;

    const linePoints: THREE.Vector3[] = [];
    for (const nb of topN) {
      linePoints.push(origin);
      linePoints.push(nb.vec);
    }

    const geom = new THREE.BufferGeometry().setFromPoints(linePoints);
    return geom;
  }, [activePos, hoveredIdx, positionsArray, trackIndices, visible]);

  if (!activePos) return null;

  return (
    <group position={activePos}>
      <mesh ref={ringRef}>
        <ringGeometry args={[0.022, 0.028, 32]} />
        <meshBasicMaterial
          color="#fa2d55"
          transparent
          opacity={0.85}
          side={THREE.DoubleSide}
          blending={THREE.AdditiveBlending}
        />
      </mesh>
      <pointLight color="#fa2d55" intensity={2.0} distance={0.3} />

      {constellationGeom && (
        <lineSegments geometry={constellationGeom} position={[-activePos[0], -activePos[1], -activePos[2]]}>
          <lineBasicMaterial
            color="#fb7185"
            transparent
            opacity={0.45}
            blending={THREE.AdditiveBlending}
          />
        </lineSegments>
      )}
    </group>
  );
}

// 7. Starfield Point Cloud Component
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
  onHoverTrack: (info: { trackIdx: number; trackId: string; regId: number; pos: [number, number, number]; rawIdx: number } | null) => void;
  onClickTrack: (trackId: string) => void;
}) {
  const pointsRef = useRef<THREE.Points | null>(null);
  const { raycaster } = useThree();
  const starTexture = useMemo(() => createStarTexture(), []);

  const maxPoints = tier === "high" ? 15000 : tier === "mid" ? 8000 : 4000;

  const { geometry, trackIndices, positionsArray } = useMemo(() => {
    const raw = data.points_quantized || (data as any).points || [];
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
        colors[pIdx * 3] = Math.min(1.0, rgb[0] * 1.25);
        colors[pIdx * 3 + 1] = Math.min(1.0, rgb[1] * 1.25);
        colors[pIdx * 3 + 2] = Math.min(1.0, rgb[2] * 1.25);
      } else {
        colors[pIdx * 3] = rgb[0] * 0.15;
        colors[pIdx * 3 + 1] = rgb[1] * 0.15;
        colors[pIdx * 3 + 2] = rgb[2] * 0.15;
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
  }, [data, maxPoints, focusedRegionId]);

  // Raycasting for point hover
  useFrame(() => {
    if (!pointsRef.current) return;
    raycaster.params.Points = { threshold: 0.038 };
    const intersects = raycaster.intersectObject(pointsRef.current);

    if (intersects.length > 0) {
      const hit = intersects[0];
      const index = hit.index;
      if (index !== undefined && index < trackIndices.length) {
        const trk = trackIndices[index];
        const reg = (data.points_quantized || (data as any).points || [])[index * 5 + 3] ?? 0;
        const actualTrackId =
          data.track_ids && trk < data.track_ids.length ? data.track_ids[trk] : `trk_${trk}`;

        const pos: [number, number, number] = [
          positionsArray[index * 3],
          positionsArray[index * 3 + 1],
          positionsArray[index * 3 + 2],
        ];
        onHoverTrack({ trackIdx: trk, trackId: actualTrackId, regId: reg, pos, rawIdx: index });
        return;
      }
    }
    onHoverTrack(null);
  });

  // Cleanup
  useEffect(() => {
    return () => {
      geometry.dispose();
      starTexture.dispose();
    };
  }, [geometry, starTexture]);

  return (
    <points
      ref={pointsRef}
      geometry={geometry}
      onClick={(e) => {
        e.stopPropagation();
        if (e.index !== undefined && e.index < trackIndices.length) {
          const trk = trackIndices[e.index];
          const actualTrackId =
            data.track_ids && trk < data.track_ids.length ? data.track_ids[trk] : `trk_${trk}`;
          onClickTrack(actualTrackId);
        }
      }}
    >
      <pointsMaterial
        size={tier === "high" ? 0.034 : 0.040}
        map={starTexture}
        vertexColors
        transparent
        alphaTest={0.005}
        opacity={0.92}
        depthWrite={false}
        blending={THREE.AdditiveBlending}
        sizeAttenuation
      />
    </points>
  );
}

// 8. Glowing Taste Beacon & Recommendation Path Arcs
function DynamicBeacons({
  recommendationCoords,
  blindspotCentroid,
}: {
  recommendationCoords?: Array<[number, number, number]>;
  blindspotCentroid?: [number, number, number] | null;
}) {
  const haloRef = useRef<THREE.Mesh | null>(null);

  useFrame(() => {
    const t = performance.now() * 0.001;
    if (haloRef.current) {
      const s = 1.0 + 0.18 * Math.sin(t * 2.8);
      haloRef.current.scale.set(s, s, s);
      haloRef.current.rotation.z = t * 0.5;
    }
  });

  const pathLineMesh = useMemo(() => {
    if (!recommendationCoords || recommendationCoords.length < 2) return null;
    const points = recommendationCoords.map((c) => new THREE.Vector3(c[0], c[1], c[2]));
    const curve = new THREE.CatmullRomCurve3(points);
    const curvePoints = curve.getPoints(Math.min(120, recommendationCoords.length * 6));
    const geom = new THREE.BufferGeometry().setFromPoints(curvePoints);
    const mat = new THREE.LineBasicMaterial({
      color: "#fa2d55",
      transparent: true,
      opacity: 0.75,
      blending: THREE.AdditiveBlending,
    });
    return new THREE.Line(geom, mat);
  }, [recommendationCoords]);

  return (
    <group>
      {pathLineMesh && <primitive object={pathLineMesh} />}

      {recommendationCoords?.map((c, i) => (
        <mesh key={i} position={[c[0], c[1], c[2]]}>
          <sphereGeometry args={[0.018, 16, 16]} />
          <meshBasicMaterial
            color={i === 0 ? "#10b981" : "#fa2d55"}
            blending={THREE.AdditiveBlending}
          />
        </mesh>
      ))}

      {blindspotCentroid && (
        <group position={[blindspotCentroid[0], blindspotCentroid[1], blindspotCentroid[2]]}>
          <mesh ref={haloRef}>
            <ringGeometry args={[0.08, 0.11, 32]} />
            <meshBasicMaterial
              color="#38bdf8"
              side={THREE.DoubleSide}
              transparent
              opacity={0.75}
              blending={THREE.AdditiveBlending}
            />
          </mesh>
          <pointLight color="#38bdf8" intensity={2.0} distance={0.6} />
        </group>
      )}
    </group>
  );
}

// 9. Camera Fly-Through & Target Tracking Controller
function CameraController({
  targetPos,
  controlsRef,
}: {
  targetPos: [number, number, number] | null;
  controlsRef: React.RefObject<OrbitControlsImpl>;
}) {
  useFrame(() => {
    if (!targetPos || !controlsRef.current) return;

    const prefersReducedMotion =
      typeof window !== "undefined" &&
      window.matchMedia("(prefers-reduced-motion: reduce)").matches;

    const targetVec = new THREE.Vector3(targetPos[0], targetPos[1], targetPos[2]);

    if (prefersReducedMotion) {
      controlsRef.current.target.copy(targetVec);
      controlsRef.current.update();
    } else {
      controlsRef.current.target.lerp(targetVec, 0.06);
      controlsRef.current.update();
    }
  });

  return null;
}

// 10. Performance Tier FPS Monitor
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
  onSelectRegion,
  onFpsReport,
  onTierChange,
  showNebulae = true,
  showLabels = true,
  showConstellations = true,
  autoRotate = true,
}: UniverseCanvas3DProps) {
  const controlsRef = useRef<OrbitControlsImpl | null>(null);
  const [hoveredTrack, setHoveredTrack] = useState<{
    trackIdx: number;
    trackId: string;
    regId: number;
    pos: [number, number, number];
    rawIdx: number;
  } | null>(null);

  const focusedInfo = useMemo<{
    pos: [number, number, number];
    rawIdx: number;
  } | null>(() => {
    if (!focusedTrackId) return null;
    const raw = data.points_quantized || (data as any).points || [];
    const stride = 5;
    const totalCount = Math.floor(raw.length / stride);

    let targetIndex = -1;
    if (data.track_ids && data.track_ids.length > 0) {
      targetIndex = data.track_ids.indexOf(focusedTrackId);
    }
    if (targetIndex === -1) {
      const match = focusedTrackId.match(/(?:trk_|track_)?(\d+)/);
      if (match) {
        const parsed = parseInt(match[1], 10);
        if (parsed >= 0 && parsed < totalCount) {
          targetIndex = parsed;
        }
      }
    }

    if (targetIndex >= 0 && targetIndex < totalCount) {
      const qx = raw[targetIndex * stride];
      const qy = raw[targetIndex * stride + 1];
      const qz = raw[targetIndex * stride + 2];
      return {
        pos: [qx / 32767.0, qy / 32767.0, qz / 32767.0],
        rawIdx: targetIndex,
      };
    }
    return null;
  }, [focusedTrackId, data]);

  const targetPos = useMemo<[number, number, number] | null>(() => {
    if (focusedInfo) {
      return focusedInfo.pos;
    }
    if (focusedRegionId !== null) {
      const reg = data.regions.find((r) => r.region_id === focusedRegionId);
      if (reg) return reg.centroid_3d;
    }
    return null;
  }, [focusedInfo, focusedRegionId, data.regions]);

  const blindspotCentroid = useMemo<[number, number, number] | null>(() => {
    if (blindspotRegionId !== null) {
      const reg = data.regions.find((r) => r.region_id === blindspotRegionId);
      if (reg) return reg.centroid_3d;
    }
    return null;
  }, [blindspotRegionId, data.regions]);

  const positionsArray = useMemo(() => {
    const raw = data.points_quantized || (data as any).points || [];
    const stride = 5;
    const totalCount = Math.floor(raw.length / stride);
    const maxPoints = tier === "high" ? 15000 : tier === "mid" ? 8000 : 4000;
    const step = Math.max(1, Math.floor(totalCount / maxPoints));
    const selectedCount = Math.ceil(totalCount / step);
    const positions = new Float32Array(selectedCount * 3);

    let pIdx = 0;
    for (let i = 0; i < totalCount; i += step) {
      const idx = i * stride;
      positions[pIdx * 3] = raw[idx] / 32767.0;
      positions[pIdx * 3 + 1] = raw[idx + 1] / 32767.0;
      positions[pIdx * 3 + 2] = raw[idx + 2] / 32767.0;
      pIdx++;
    }
    return positions.subarray(0, pIdx * 3);
  }, [data, tier]);

  const trackIndices = useMemo(() => {
    const raw = data.points_quantized || (data as any).points || [];
    const stride = 5;
    const totalCount = Math.floor(raw.length / stride);
    const maxPoints = tier === "high" ? 15000 : tier === "mid" ? 8000 : 4000;
    const step = Math.max(1, Math.floor(totalCount / maxPoints));
    const selectedCount = Math.ceil(totalCount / step);
    const tIndices = new Int32Array(selectedCount);

    let pIdx = 0;
    for (let i = 0; i < totalCount; i += step) {
      tIndices[pIdx] = raw[i * stride + 4];
      pIdx++;
    }
    return tIndices.subarray(0, pIdx);
  }, [data, tier]);

  return (
    <div
      className="relative w-full h-full select-none"
      style={{
        background: "radial-gradient(circle at 50% 50%, #0d1222 0%, #060914 60%, #030408 100%)",
      }}
    >
      <Canvas
        camera={{ position: [0, 0, 2.2], fov: 60, near: 0.01, far: 50 }}
        gl={{ antialias: true, alpha: true, powerPreference: "high-performance" }}
        dpr={tier === "mobile" ? 1.0 : [1, 2]}
      >
        <ambientLight intensity={0.7} />
        <pointLight position={[5, 5, 5]} intensity={1.0} />

        <OrbitControls
          ref={controlsRef}
          enableDamping
          dampingFactor={0.06}
          rotateSpeed={0.8}
          zoomSpeed={1.1}
          minDistance={0.2}
          maxDistance={5.0}
          autoRotate={autoRotate}
          autoRotateSpeed={0.35}
        />

        {/* 1. Deep Space Cosmic Dust */}
        <CosmicDust />

        {/* 2. Volumetric Cluster Nebulae */}
        <RegionNebulae
          regions={data.regions}
          focusedRegionId={focusedRegionId}
          visible={showNebulae}
        />

        {/* 3. Starfield Catalog Points */}
        <Starfield
          data={data}
          tier={tier}
          focusedRegionId={focusedRegionId}
          onHoverTrack={setHoveredTrack}
          onClickTrack={onSelectTrack}
        />

        {/* 4. Floating 3D Region Labels */}
        <RegionLabels
          regions={data.regions}
          focusedRegionId={focusedRegionId}
          onSelectRegion={onSelectRegion}
          visible={showLabels}
        />

        {/* 5. Holographic Selection Reticle & Constellation Web */}
        <StarSelectionOverlay
          hoveredPos={hoveredTrack?.pos ?? null}
          focusedPos={focusedInfo?.pos ?? null}
          positionsArray={positionsArray}
          trackIndices={trackIndices}
          hoveredIdx={hoveredTrack?.rawIdx ?? focusedInfo?.rawIdx ?? null}
          visible={showConstellations}
        />

        {/* 6. Glowing Taste Beacon & Recommendation Journey Arc */}
        <DynamicBeacons
          recommendationCoords={recommendationCoords}
          blindspotCentroid={blindspotCentroid}
        />

        {/* 7. Camera Tracking Controller */}
        <CameraController targetPos={targetPos} controlsRef={controlsRef} />

        {/* 8. FPS Monitor */}
        <FpsMonitor
          onFpsReport={onFpsReport}
          onTierChange={onTierChange}
          currentTier={tier}
        />
      </Canvas>

      {/* Floating Hover Card */}
      {hoveredTrack && (
        <div className="pointer-events-none absolute bottom-16 left-1/2 -translate-x-1/2 z-20 px-4 py-2.5 rounded-2xl bg-[#0d101a]/90 border border-white/20 text-xs text-white shadow-2xl backdrop-blur-2xl flex items-center gap-3 animate-in fade-in duration-150">
          <span
            className="w-3.5 h-3.5 rounded-full shadow-[0_0_10px_currentColor]"
            style={{
              backgroundColor:
                REGION_PALETTE_HEX[hoveredTrack.regId % REGION_PALETTE_HEX.length],
              color:
                REGION_PALETTE_HEX[hoveredTrack.regId % REGION_PALETTE_HEX.length],
            }}
          />
          <div>
            <p className="font-bold text-white text-xs">Star #{hoveredTrack.trackIdx}</p>
            <p className="text-[10px] text-white/60">
              Region {hoveredTrack.regId}:{" "}
              <strong className="text-white/90">
                {data.regions.find((r) => r.region_id === hoveredTrack.regId)?.name || "Catalog Cluster"}
              </strong>
            </p>
          </div>
          <span className="text-[10px] text-[#fb7185] font-mono pl-3 border-l border-white/10 font-semibold">
            Click to inspect
          </span>
        </div>
      )}
    </div>
  );
}
