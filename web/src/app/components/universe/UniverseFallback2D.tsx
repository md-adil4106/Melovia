"use client";

import React, { useRef, useEffect, useState, useMemo } from "react";
import {
  ZoomIn,
  ZoomOut,
  RotateCcw,
  Compass,
  Table as TableIcon,
  MapPin,
  Sparkles,
} from "lucide-react";
import { UniverseData, REGION_PALETTE_HEX } from "./types";

interface UniverseFallback2DProps {
  data: UniverseData;
  focusedRegionId: number | null;
  onSelectRegion: (regionId: number) => void;
  onSelectTrack: (trackId: string) => void;
}

export function UniverseFallback2D({
  data,
  focusedRegionId,
  onSelectRegion,
  onSelectTrack,
}: UniverseFallback2DProps) {
  const canvasRef = useRef<HTMLCanvasElement | null>(null);
  const [scale, setScale] = useState(1.0);
  const [offset, setOffset] = useState({ x: 0, y: 0 });
  const [isDragging, setIsDragging] = useState(false);
  const [dragStart, setDragStart] = useState({ x: 0, y: 0 });
  const [hoveredPoint, setHoveredPoint] = useState<{
    trackIdx: number;
    regId: number;
    screenX: number;
    screenY: number;
  } | null>(null);
  const [showTable, setShowTable] = useState(false);

  // Subsample points for 2D canvas drawing (max 6,000 points for smooth 2D canvas drawing)
  const renderPoints = useMemo(() => {
    const raw = data.points_quantized;
    const stride = 5;
    const totalPoints = Math.floor(raw.length / stride);
    const step = Math.max(1, Math.floor(totalPoints / 6000));
    const pts: Array<{ x: number; y: number; reg: number; trk: number }> = [];

    for (let i = 0; i < totalPoints; i += step) {
      const idx = i * stride;
      pts.push({
        x: raw[idx] / 32767.0,
        y: raw[idx + 1] / 32767.0,
        reg: raw[idx + 3],
        trk: raw[idx + 4],
      });
    }
    return pts;
  }, [data.points_quantized]);

  // Redraw canvas
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    const width = canvas.width;
    const height = canvas.height;

    // Clear canvas
    ctx.fillStyle = "#0c0f17";
    ctx.fillRect(0, 0, width, height);

    // Draw coordinate grid lines
    ctx.strokeStyle = "#161c28";
    ctx.lineWidth = 1;
    const centerX = width / 2 + offset.x;
    const centerY = height / 2 + offset.y;

    ctx.beginPath();
    ctx.moveTo(0, centerY);
    ctx.lineTo(width, centerY);
    ctx.moveTo(centerX, 0);
    ctx.lineTo(centerX, height);
    ctx.stroke();

    // Draw points
    const baseRadius = Math.max(1.5, Math.min(4, 2 * scale));

    for (let i = 0; i < renderPoints.length; i++) {
      const p = renderPoints[i];
      const isFocused = focusedRegionId === null || p.reg === focusedRegionId;

      const px = centerX + p.x * (width * 0.42) * scale;
      const py = centerY + p.y * (height * 0.42) * scale;

      // Skip off-screen points
      if (px < -10 || px > width + 10 || py < -10 || py > height + 10) continue;

      ctx.fillStyle = isFocused
        ? REGION_PALETTE_HEX[p.reg % REGION_PALETTE_HEX.length]
        : "#242d3d";
      ctx.globalAlpha = isFocused ? 0.75 : 0.15;

      ctx.beginPath();
      ctx.arc(px, py, isFocused ? baseRadius : 1.2, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.globalAlpha = 1.0;

    // Draw region centroids
    data.regions.forEach((reg) => {
      const isFocused = focusedRegionId === reg.region_id;
      const rx = centerX + reg.centroid_3d[0] * (width * 0.42) * scale;
      const ry = centerY + reg.centroid_3d[1] * (height * 0.42) * scale;

      if (rx >= 0 && rx <= width && ry >= 0 && ry <= height) {
        ctx.fillStyle = REGION_PALETTE_HEX[reg.region_id % REGION_PALETTE_HEX.length];
        ctx.strokeStyle = isFocused ? "#ffffff" : "#0d1017";
        ctx.lineWidth = isFocused ? 2.5 : 1.5;

        ctx.beginPath();
        ctx.arc(rx, ry, isFocused ? 7 : 5, 0, Math.PI * 2);
        ctx.fill();
        ctx.stroke();

        // Centroid label
        ctx.font = isFocused ? "bold 11px sans-serif" : "10px sans-serif";
        ctx.fillStyle = isFocused ? "#ffffff" : "#8c96a8";
        ctx.fillText(reg.name, rx + 8, ry + 3);
      }
    });
  }, [renderPoints, data.regions, scale, offset, focusedRegionId]);

  // Resize canvas according to container
  useEffect(() => {
    const handleResize = () => {
      const canvas = canvasRef.current;
      if (canvas && canvas.parentElement) {
        canvas.width = canvas.parentElement.clientWidth;
        canvas.height = canvas.parentElement.clientHeight;
      }
    };
    handleResize();
    window.addEventListener("resize", handleResize);
    return () => window.removeEventListener("resize", handleResize);
  }, []);

  const handleMouseDown = (e: React.MouseEvent<HTMLCanvasElement>) => {
    setIsDragging(true);
    setDragStart({ x: e.clientX - offset.x, y: e.clientY - offset.y });
  };

  const handleMouseMove = (e: React.MouseEvent<HTMLCanvasElement>) => {
    if (isDragging) {
      setOffset({
        x: e.clientX - dragStart.x,
        y: e.clientY - dragStart.y,
      });
      return;
    }

    // Hit-testing nearest point
    const canvas = canvasRef.current;
    if (!canvas) return;
    const rect = canvas.getBoundingClientRect();
    const mx = e.clientX - rect.left;
    const my = e.clientY - rect.top;

    const width = canvas.width;
    const height = canvas.height;
    const centerX = width / 2 + offset.x;
    const centerY = height / 2 + offset.y;

    let closest: typeof hoveredPoint = null;
    let minDist = 15; // 15px radius

    for (let i = 0; i < renderPoints.length; i++) {
      const p = renderPoints[i];
      const px = centerX + p.x * (width * 0.42) * scale;
      const py = centerY + p.y * (height * 0.42) * scale;
      const dist = Math.hypot(mx - px, my - py);

      if (dist < minDist) {
        minDist = dist;
        closest = {
          trackIdx: p.trk,
          regId: p.reg,
          screenX: px,
          screenY: py,
        };
      }
    }
    setHoveredPoint(closest);
  };

  const handleMouseUp = () => setIsDragging(false);

  const handleClick = () => {
    if (hoveredPoint) {
      onSelectTrack(`trk_${hoveredPoint.trackIdx}`);
    }
  };

  const handleWheel = (e: React.WheelEvent<HTMLCanvasElement>) => {
    e.preventDefault();
    const zoomDelta = e.deltaY < 0 ? 1.15 : 0.87;
    setScale((prev) => Math.max(0.4, Math.min(6.0, prev * zoomDelta)));
  };

  return (
    <div className="relative w-full h-full flex flex-col bg-[#0c0f17] select-none">
      {/* 2D Mode Banner */}
      <div className="bg-[#141924] border-b border-[#202738] px-4 py-2 flex items-center justify-between text-xs text-[#8c96a8]">
        <div className="flex items-center gap-2">
          <span className="w-2 h-2 rounded-full bg-sky-400" />
          <span className="font-semibold text-[#c8d0de]">2D Canvas Fallback View</span>
          <span className="text-[10px] text-[#647187]">
            (Trustworthiness k=15: {(data.quality_metrics.trustworthiness_k15 * 100).toFixed(1)}%)
          </span>
        </div>

        <div className="flex items-center gap-2">
          <button
            type="button"
            onClick={() => setShowTable(!showTable)}
            className="flex items-center gap-1 px-2.5 py-1 rounded-lg bg-[#1a2230] hover:bg-[#252f44] text-[#c8d0de] border border-[#2b374c] transition-colors"
          >
            <TableIcon className="w-3 h-3" />
            <span>{showTable ? "Hide Region Table" : "Accessible Region Table"}</span>
          </button>
        </div>
      </div>

      {/* Main View Area */}
      <div className="relative flex-1 w-full h-full overflow-hidden">
        <canvas
          ref={canvasRef}
          onMouseDown={handleMouseDown}
          onMouseMove={handleMouseMove}
          onMouseUp={handleMouseUp}
          onMouseLeave={handleMouseUp}
          onClick={handleClick}
          onWheel={handleWheel}
          className="w-full h-full cursor-grab active:cursor-grabbing"
          aria-label="2D Scatter plot of music universe"
        />

        {/* Floating Tooltip */}
        {hoveredPoint && (
          <div
            className="pointer-events-none absolute z-20 px-3 py-1.5 rounded-lg bg-[#141924]/95 border border-[#d4af37]/60 text-xs text-[#f1f3f7] shadow-xl backdrop-blur-sm -translate-x-1/2 -translate-y-full -mt-2"
            style={{ left: hoveredPoint.screenX, top: hoveredPoint.screenY }}
          >
            <p className="font-bold text-[#d4af37]">Track #{hoveredPoint.trackIdx}</p>
            <p className="text-[10px] text-[#8c96a8]">
              Region {hoveredPoint.regId}: {data.regions[hoveredPoint.regId]?.name || "Unknown"}
            </p>
            <p className="text-[9px] text-[#647187] italic">Click to inspect in manifold</p>
          </div>
        )}

        {/* Zoom & Pan Controls Overlay */}
        <div className="absolute bottom-4 left-4 flex items-center gap-1.5 bg-[#121620]/90 border border-[#222a3b] rounded-xl p-1.5 shadow-lg backdrop-blur-md z-10">
          <button
            type="button"
            onClick={() => setScale((s) => Math.min(6.0, s * 1.25))}
            aria-label="Zoom in"
            className="p-1.5 rounded-lg hover:bg-[#1c2436] text-[#8c96a8] hover:text-[#f1f3f7] transition-colors"
          >
            <ZoomIn className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => setScale((s) => Math.max(0.4, s * 0.8))}
            aria-label="Zoom out"
            className="p-1.5 rounded-lg hover:bg-[#1c2436] text-[#8c96a8] hover:text-[#f1f3f7] transition-colors"
          >
            <ZoomOut className="w-4 h-4" />
          </button>
          <button
            type="button"
            onClick={() => {
              setScale(1.0);
              setOffset({ x: 0, y: 0 });
            }}
            aria-label="Reset zoom and center"
            className="p-1.5 rounded-lg hover:bg-[#1c2436] text-[#8c96a8] hover:text-[#f1f3f7] transition-colors"
          >
            <RotateCcw className="w-4 h-4" />
          </button>
          <span className="text-[10px] font-mono text-[#8c96a8] px-1.5">
            {Math.round(scale * 100)}%
          </span>
        </div>

        {/* Accessible Region Table Overlay */}
        {showTable && (
          <div className="absolute inset-0 bg-[#0c0f17]/95 backdrop-blur-md p-6 overflow-y-auto z-30 animate-in fade-in duration-200">
            <div className="max-w-4xl mx-auto space-y-4">
              <div className="flex items-center justify-between pb-3 border-b border-[#202738]">
                <div>
                  <h4 className="text-base font-bold text-[#f1f3f7] flex items-center gap-2">
                    <Compass className="w-4 h-4 text-[#d4af37]" />
                    Accessible Region Catalog Summary
                  </h4>
                  <p className="text-xs text-[#8c96a8]">
                    Text alternative for screen readers and keyboard navigation. Select any region
                    to focus.
                  </p>
                </div>
                <button
                  type="button"
                  onClick={() => setShowTable(false)}
                  className="px-3 py-1.5 bg-[#1b2230] text-xs font-semibold text-[#c8d0de] rounded-lg border border-[#2d374d]"
                >
                  Close Table
                </button>
              </div>

              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs border-collapse">
                  <thead>
                    <tr className="border-b border-[#252f44] text-[#8c96a8]">
                      <th className="py-2.5 px-3">Region</th>
                      <th className="py-2.5 px-3">Cluster Label</th>
                      <th className="py-2.5 px-3">Genre Focus</th>
                      <th className="py-2.5 px-3">3D Centroid (x, y, z)</th>
                      <th className="py-2.5 px-3">Exposure</th>
                      <th className="py-2.5 px-3">Action</th>
                    </tr>
                  </thead>
                  <tbody className="divide-y divide-[#18202d]">
                    {data.regions.map((r) => {
                      const color = REGION_PALETTE_HEX[r.region_id % REGION_PALETTE_HEX.length];
                      const isFocused = focusedRegionId === r.region_id;
                      return (
                        <tr
                          key={r.region_id}
                          className={`hover:bg-[#151b27] transition-colors ${
                            isFocused ? "bg-[#182233]" : ""
                          }`}
                        >
                          <td className="py-2.5 px-3 font-mono font-bold flex items-center gap-2">
                            <span
                              className="w-2.5 h-2.5 rounded-full inline-block"
                              style={{ backgroundColor: color }}
                            />
                            <span>R{r.region_id}</span>
                          </td>
                          <td className="py-2.5 px-3 font-semibold text-[#f1f3f7]">{r.name}</td>
                          <td className="py-2.5 px-3 text-[#c8d0de]">{r.genre_focus}</td>
                          <td className="py-2.5 px-3 font-mono text-[#8c96a8]">
                            [{r.centroid_3d.map((v) => v.toFixed(2)).join(", ")}]
                          </td>
                          <td className="py-2.5 px-3 font-mono text-[#d4af37]">
                            {(r.exposure * 100).toFixed(1)}%
                          </td>
                          <td className="py-2.5 px-3">
                            <button
                              type="button"
                              onClick={() => {
                                onSelectRegion(r.region_id);
                                setShowTable(false);
                              }}
                              className="px-2.5 py-1 bg-[#1e2638] hover:bg-[#d4af37] text-[#c8d0de] hover:text-black font-semibold rounded text-[11px] transition-colors"
                            >
                              Focus
                            </button>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
