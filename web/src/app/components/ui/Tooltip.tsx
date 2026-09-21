import React, { useState } from "react";
import { cn } from "./utils";

export interface TooltipProps {
  content: React.ReactNode;
  children: React.ReactNode;
  className?: string;
  side?: "top" | "bottom" | "left" | "right";
}

export function Tooltip({ content, children, className, side = "top" }: TooltipProps) {
  const [isVisible, setIsVisible] = useState(false);

  const sideStyles = {
    top: "bottom-full left-1/2 -translate-x-1/2 mb-2",
    bottom: "top-full left-1/2 -translate-x-1/2 mt-2",
    left: "right-full top-1/2 -translate-y-1/2 mr-2",
    right: "left-full top-1/2 -translate-y-1/2 ml-2",
  };

  return (
    <div
      className="relative inline-flex"
      onMouseEnter={() => setIsVisible(true)}
      onMouseLeave={() => setIsVisible(false)}
      onFocus={() => setIsVisible(true)}
      onBlur={() => setIsVisible(false)}
    >
      {children}
      {isVisible && (
        <div
          role="tooltip"
          className={cn(
            "absolute z-50 px-3 py-1.5 text-xs text-[#f1f3f7] bg-[#1a2230] border border-[#2c374d] rounded-lg shadow-xl pointer-events-none whitespace-normal max-w-xs animate-in fade-in duration-150",
            sideStyles[side],
            className
          )}
        >
          {content}
        </div>
      )}
    </div>
  );
}
