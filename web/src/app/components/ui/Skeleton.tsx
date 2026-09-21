import React from "react";
import { cn } from "./utils";

export interface SkeletonProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "text" | "rectangular" | "circular";
}

export function Skeleton({ className, variant = "rectangular", ...props }: SkeletonProps) {
  return (
    <div
      className={cn(
        "animate-pulse bg-[#1a2230]/70",
        variant === "text" && "h-4 w-full rounded",
        variant === "rectangular" && "rounded-xl",
        variant === "circular" && "rounded-full",
        className
      )}
      {...props}
    />
  );
}

export function TrackItemSkeleton() {
  return (
    <div className="p-4 bg-[#141923] border border-[#232a3b] rounded-xl flex items-center justify-between gap-4">
      <div className="flex items-center gap-3.5 flex-1 min-w-0">
        <Skeleton variant="circular" className="w-10 h-10 shrink-0" />
        <div className="space-y-2 flex-1 min-w-0">
          <Skeleton variant="text" className="w-1/3 h-4" />
          <Skeleton variant="text" className="w-1/4 h-3" />
        </div>
      </div>
      <div className="flex items-center gap-2 shrink-0">
        <Skeleton variant="rectangular" className="w-8 h-8 rounded-lg" />
        <Skeleton variant="rectangular" className="w-8 h-8 rounded-lg" />
      </div>
    </div>
  );
}
