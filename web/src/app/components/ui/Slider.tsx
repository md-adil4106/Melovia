import React from "react";
import { cn } from "./utils";

export interface SliderProps extends Omit<React.InputHTMLAttributes<HTMLInputElement>, "onChange"> {
  value: number;
  min?: number;
  max?: number;
  step?: number;
  label?: string;
  onChange: (val: number) => void;
  accentColor?: "warm" | "cool";
}

export function Slider({
  className,
  value,
  min = 0,
  max = 100,
  step = 1,
  label = "Slider control",
  onChange,
  accentColor = "warm",
  disabled = false,
  ...props
}: SliderProps) {
  const pct = Math.min(100, Math.max(0, ((value - min) / (max - min)) * 100));

  const handleKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (disabled) return;
    let nextVal = value;
    if (e.key === "ArrowLeft" || e.key === "ArrowDown") {
      nextVal = Math.max(min, value - step);
    } else if (e.key === "ArrowRight" || e.key === "ArrowUp") {
      nextVal = Math.min(max, value + step);
    } else if (e.key === "Home") {
      nextVal = min;
    } else if (e.key === "End") {
      nextVal = max;
    } else {
      return;
    }
    e.preventDefault();
    onChange(nextVal);
  };

  return (
    <div className={cn("relative flex items-center w-full select-none touch-none", className)}>
      <input
        type="range"
        min={min}
        max={max}
        step={step}
        value={value}
        disabled={disabled}
        aria-label={label}
        aria-valuenow={value}
        aria-valuemin={min}
        aria-valuemax={max}
        onKeyDown={handleKeyDown}
        onChange={(e) => onChange(parseFloat(e.target.value))}
        className="w-full h-2 bg-white/10 rounded-full appearance-none cursor-pointer focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ruby disabled:opacity-40 disabled:cursor-not-allowed"
        style={{
          background: `linear-gradient(to right, ${
            accentColor === "warm" ? "#fa2d55" : "#38bdf8"
          } 0%, ${
            accentColor === "warm" ? "#fb7185" : "#38bdf8"
          } ${pct}%, rgba(255, 255, 255, 0.1) ${pct}%, rgba(255, 255, 255, 0.1) 100%)`,
        }}
        {...props}
      />
    </div>
  );
}
