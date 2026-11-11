"use client";

import React, { useEffect, useRef, useState } from "react";

/**
 * RefractionAura: Subtle cursor-following liquid refraction glow.
 * Renders behind liquid glass panels to create modern spatial depth
 * (inspired by ThreeUI, GSAP, and 21st.dev).
 * Strictly honors prefers-reduced-motion and cleans up listeners.
 */
export function RefractionAura() {
  const auraRef = useRef<HTMLDivElement>(null);
  const [isVisible, setIsVisible] = useState(false);

  useEffect(() => {
    // Check for reduced motion preference safely (supporting JSDOM environments)
    if (typeof window.matchMedia === "function") {
      const mediaQuery = window.matchMedia("(prefers-reduced-motion: reduce)");
      if (mediaQuery.matches) return;
    }

    let targetX = window.innerWidth / 2;
    let targetY = window.innerHeight / 2;
    let currentX = targetX;
    let currentY = targetY;
    let animationFrameId: number;
    let isTracking = false;

    const handlePointerMove = (e: PointerEvent) => {
      targetX = e.clientX;
      targetY = e.clientY;
      if (!isTracking) {
        isTracking = true;
        setIsVisible(true);
      }
    };

    const handlePointerLeave = () => {
      setIsVisible(false);
    };

    const animate = () => {
      // Smooth lerp interpolation for silky motion
      currentX += (targetX - currentX) * 0.08;
      currentY += (targetY - currentY) * 0.08;

      if (auraRef.current) {
        auraRef.current.style.transform = `translate3d(${currentX}px, ${currentY}px, 0)`;
      }

      animationFrameId = requestAnimationFrame(animate);
    };

    window.addEventListener("pointermove", handlePointerMove, { passive: true });
    document.addEventListener("mouseleave", handlePointerLeave);
    animationFrameId = requestAnimationFrame(animate);

    return () => {
      window.removeEventListener("pointermove", handlePointerMove);
      document.removeEventListener("mouseleave", handlePointerLeave);
      cancelAnimationFrame(animationFrameId);
    };
  }, []);

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-0 z-0 overflow-hidden"
    >
      <div
        ref={auraRef}
        className={`absolute -top-64 -left-64 h-[32rem] w-[32rem] rounded-full transition-opacity duration-700 ease-out ${
          isVisible ? "opacity-100" : "opacity-0"
        }`}
        style={{
          background:
            "radial-gradient(circle, rgba(250, 45, 85, 0.12) 0%, rgba(139, 92, 246, 0.08) 40%, rgba(56, 189, 248, 0.03) 70%, transparent 100%)",
          filter: "blur(60px)",
          willChange: "transform",
        }}
      />
    </div>
  );
}
