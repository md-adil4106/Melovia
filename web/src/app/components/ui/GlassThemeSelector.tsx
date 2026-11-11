"use client";

import React, { useEffect } from "react";
import { Sparkles, Layers } from "lucide-react";
import { useDiscoveryStore } from "../../store";

interface GlassThemeSelectorProps {
  variant?: "compact" | "detailed";
  className?: string;
}

export function GlassThemeSelector({
  variant = "compact",
  className = "",
}: GlassThemeSelectorProps) {
  const { glassTheme, setGlassTheme } = useDiscoveryStore();

  // Initialize theme from localStorage on client mount
  useEffect(() => {
    try {
      const stored = localStorage.getItem("melovia_glass_theme");
      if (stored === "clear" || stored === "frosted") {
        setGlassTheme(stored);
      } else {
        document.documentElement.setAttribute("data-glass-theme", "clear");
      }
    } catch {
      document.documentElement.setAttribute("data-glass-theme", "clear");
    }
  }, [setGlassTheme]);

  if (variant === "detailed") {
    return (
      <div className={`space-y-2.5 ${className}`}>
        <label className="text-xs font-semibold uppercase tracking-wider text-white/60 block">
          Glass Material Style
        </label>
        <div className="grid grid-cols-2 gap-2">
          <button
            type="button"
            data-testid="glass-theme-clear"
            aria-pressed={glassTheme === "clear"}
            aria-label="Switch to Clear Liquid Glass effect"
            onClick={() => setGlassTheme("clear")}
            className={`p-3 rounded-2xl border text-left transition-all ${
              glassTheme === "clear"
                ? "bg-gradient-to-tr from-[#fa2d55]/20 to-[#8b5cf6]/20 border-[#fa2d55]/60 text-white shadow-[0_0_20px_rgba(250,45,85,0.25)]"
                : "glass-card text-white/70 hover:text-white hover:border-white/20"
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <Sparkles className="w-4 h-4 text-[#fa2d55]" />
              <span className="text-xs font-bold text-white">Clear Liquid</span>
            </div>
            <p className="text-[11px] text-white/50 leading-relaxed">
              Ultra-translucent acrylic with sharp specular rim highlights and deep refraction.
            </p>
          </button>

          <button
            type="button"
            data-testid="glass-theme-frosted"
            aria-pressed={glassTheme === "frosted"}
            aria-label="Switch to Frosted Acrylic Glass effect"
            onClick={() => setGlassTheme("frosted")}
            className={`p-3 rounded-2xl border text-left transition-all ${
              glassTheme === "frosted"
                ? "bg-gradient-to-tr from-[#fa2d55]/20 to-[#8b5cf6]/20 border-[#fa2d55]/60 text-white shadow-[0_0_20px_rgba(250,45,85,0.25)]"
                : "glass-card text-white/70 hover:text-white hover:border-white/20"
            }`}
          >
            <div className="flex items-center gap-2 mb-1">
              <Layers className="w-4 h-4 text-[#8b5cf6]" />
              <span className="text-xs font-bold text-white">Frosted Matte</span>
            </div>
            <p className="text-[11px] text-white/50 leading-relaxed">
              Silky frosted glass with heavy milky diffusion and velvety matte lighting.
            </p>
          </button>
        </div>
      </div>
    );
  }

  return (
    <div
      role="group"
      aria-label="Glass Material Effect"
      className={`inline-flex items-center bg-black/40 border border-white/10 rounded-full p-0.5 backdrop-blur-xl ${className}`}
    >
      <button
        type="button"
        data-testid="glass-theme-clear"
        aria-pressed={glassTheme === "clear"}
        aria-label="Clear Glass"
        onClick={() => setGlassTheme("clear")}
        className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold transition-all ${
          glassTheme === "clear"
            ? "bg-white/[0.18] text-white shadow-sm border border-white/20"
            : "text-white/60 hover:text-white"
        }`}
      >
        <Sparkles className="w-3 h-3 text-[#fa2d55]" />
        <span>Clear</span>
      </button>

      <button
        type="button"
        data-testid="glass-theme-frosted"
        aria-pressed={glassTheme === "frosted"}
        aria-label="Frosted Glass"
        onClick={() => setGlassTheme("frosted")}
        className={`flex items-center gap-1.5 px-3 py-1 rounded-full text-xs font-semibold transition-all ${
          glassTheme === "frosted"
            ? "bg-white/[0.18] text-white shadow-sm border border-white/20"
            : "text-white/60 hover:text-white"
        }`}
      >
        <Layers className="w-3 h-3 text-[#c084fc]" />
        <span>Frosted</span>
      </button>
    </div>
  );
}
