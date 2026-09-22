import React from "react";
import { cn } from "./utils";

export interface CardProps extends React.HTMLAttributes<HTMLDivElement> {
  variant?: "default" | "elevated" | "interactive";
}

export function Card({ className, variant = "default", children, ...props }: CardProps) {
  return (
    <div
      className={cn(
        "rounded-2xl border border-white/[0.08] p-6 transition-all duration-250",
        variant === "default" && "bg-white/[0.035] backdrop-blur-xl shadow-[0_8px_32px_rgba(0,0,0,0.4)]",
        variant === "elevated" && "bg-white/[0.06] backdrop-blur-2xl border-white/[0.14] shadow-2xl",
        variant === "interactive" &&
          "bg-white/[0.035] backdrop-blur-xl hover:border-white/[0.18] hover:bg-white/[0.07] cursor-pointer hover:shadow-lg",
        className
      )}
      {...props}
    >
      {children}
    </div>
  );
}

export function CardHeader({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("flex flex-col space-y-1.5 mb-4", className)} {...props}>
      {children}
    </div>
  );
}

export function CardTitle({ className, children, ...props }: React.HTMLAttributes<HTMLHeadingElement>) {
  return (
    <h3
      className={cn("text-lg font-bold text-ink-text tracking-tight", className)}
      {...props}
    >
      {children}
    </h3>
  );
}

export function CardDescription({
  className,
  children,
  ...props
}: React.HTMLAttributes<HTMLParagraphElement>) {
  return (
    <p className={cn("text-xs sm:text-sm text-ink-muted leading-relaxed", className)} {...props}>
      {children}
    </p>
  );
}

export function CardContent({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div className={cn("", className)} {...props}>{children}</div>;
}

export function CardFooter({ className, children, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return (
    <div className={cn("mt-4 pt-4 border-t border-ink-border flex items-center", className)} {...props}>
      {children}
    </div>
  );
}
